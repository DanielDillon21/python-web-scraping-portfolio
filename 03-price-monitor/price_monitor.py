"""
Price & stock monitor built with requests + BeautifulSoup + SQLite.

Reads a watchlist of product URLs, fetches each one, and records a price/stock
snapshot in a local SQLite database. Every run is compared with the previous
snapshot so the monitor can raise alerts:

    PRICE_DROP      price went down since last check
    PRICE_INCREASE  price went up since last check
    BELOW_TARGET    price is at or under your target price
    BACK_IN_STOCK   item was unavailable and is now in stock
    OUT_OF_STOCK    item just sold out
    LOW_STOCK       few units left

Designed to run on a schedule (Windows Task Scheduler / cron), so the
history builds up over days and weeks.

Run:
    python price_monitor.py                       # uses watchlist.csv
    python price_monitor.py --watchlist my.csv
Outputs:
    output/price_history.db    every snapshot ever taken
    output/alerts.csv          alerts from the latest run
    output/price_report.xlsx   latest prices, alerts, full history
"""

import argparse
import csv
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"
DB_PATH = OUTPUT_DIR / "price_history.db"

LOW_STOCK_UNITS = 3
REQUEST_DELAY_SECONDS = 0.5
USER_AGENT = "portfolio-price-monitor (+https://www.upwork.com/freelancers/~0181ce0b02be19129c)"


# ---------------------------------------------------------------- fetching

def make_session():
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def parse_product(html):
    """Extract title, price and stock from a product page. Pure function, easy to test."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("div.product_main h1")
    price = soup.select_one("div.product_main p.price_color")
    availability = soup.select_one("div.product_main p.availability")

    stock_text = availability.get_text(" ", strip=True) if availability else ""
    stock_match = re.search(r"\((\d+) available\)", stock_text)

    return {
        "title": title.get_text(strip=True) if title else None,
        "price": float(re.sub(r"[^\d.]", "", price.get_text())) if price else None,
        "stock": int(stock_match.group(1)) if stock_match else 0,
    }


# ---------------------------------------------------------------- storage

def connect(db_path=DB_PATH):
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS snapshots (
               id         INTEGER PRIMARY KEY,
               checked_at TEXT NOT NULL,
               url        TEXT NOT NULL,
               title      TEXT,
               price      REAL,
               stock      INTEGER
           )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_url_time ON snapshots (url, checked_at)")
    return conn


def last_snapshot(conn, url):
    row = conn.execute(
        "SELECT price, stock FROM snapshots WHERE url = ? ORDER BY checked_at DESC, id DESC LIMIT 1",
        (url,),
    ).fetchone()
    return {"price": row[0], "stock": row[1]} if row else None


def save_snapshot(conn, checked_at, url, product):
    conn.execute(
        "INSERT INTO snapshots (checked_at, url, title, price, stock) VALUES (?, ?, ?, ?, ?)",
        (checked_at, url, product["title"], product["price"], product["stock"]),
    )


# ---------------------------------------------------------------- alerting

def detect_events(previous, current, target_price=None):
    """Compare two snapshots and return a list of (event, detail) tuples."""
    events = []
    price, stock = current["price"], current["stock"]

    if previous is not None and previous["price"] is not None and price is not None:
        change = round(price - previous["price"], 2)
        if change < 0:
            events.append(("PRICE_DROP", f"{previous['price']:.2f} -> {price:.2f} ({change:+.2f})"))
        elif change > 0:
            events.append(("PRICE_INCREASE", f"{previous['price']:.2f} -> {price:.2f} ({change:+.2f})"))

    if target_price is not None and price is not None and price <= target_price:
        events.append(("BELOW_TARGET", f"{price:.2f} <= target {target_price:.2f}"))

    if previous is not None:
        if previous["stock"] == 0 and stock > 0:
            events.append(("BACK_IN_STOCK", f"{stock} available"))
        elif previous["stock"] > 0 and stock == 0:
            events.append(("OUT_OF_STOCK", "sold out"))

    if 0 < stock <= LOW_STOCK_UNITS:
        events.append(("LOW_STOCK", f"only {stock} left"))

    return events


# ---------------------------------------------------------------- reporting

def read_watchlist(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [
            {"url": row["url"].strip(), "target_price": float(row["target_price"]) if row.get("target_price") else None}
            for row in csv.DictReader(f)
            if row.get("url", "").strip()
        ]


def write_reports(conn, alerts):
    pd.DataFrame(alerts, columns=["checked_at", "title", "event", "detail", "url"]).to_csv(
        OUTPUT_DIR / "alerts.csv", index=False, encoding="utf-8-sig"
    )

    history = pd.read_sql_query("SELECT checked_at, title, price, stock, url FROM snapshots ORDER BY checked_at", conn)
    latest = history.groupby("url").tail(1)
    stats = (
        history.groupby("url")
        .agg(lowest_seen=("price", "min"), highest_seen=("price", "max"), checks=("price", "count"))
        .reset_index()
    )
    latest = latest.merge(stats, on="url")[
        ["title", "price", "lowest_seen", "highest_seen", "stock", "checks", "checked_at", "url"]
    ]

    with pd.ExcelWriter(OUTPUT_DIR / "price_report.xlsx", engine="openpyxl") as writer:
        sheets = {
            "Latest Prices": latest,
            "Alerts": pd.DataFrame(alerts, columns=["checked_at", "title", "event", "detail", "url"]),
            "History": history,
        }
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(width + 2, 70)


# ---------------------------------------------------------------- main

def run(watchlist_path):
    watchlist = read_watchlist(watchlist_path)
    session = make_session()
    conn = connect()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    alerts = []

    for item in watchlist:
        try:
            response = session.get(item["url"], timeout=20)
            response.raise_for_status()
            response.encoding = "utf-8"
        except requests.RequestException as exc:
            print(f"[error] {item['url']}: {exc}")
            alerts.append((checked_at, None, "FETCH_FAILED", str(exc), item["url"]))
            continue

        product = parse_product(response.text)
        previous = last_snapshot(conn, item["url"])
        for event, detail in detect_events(previous, product, item["target_price"]):
            alerts.append((checked_at, product["title"], event, detail, item["url"]))

        save_snapshot(conn, checked_at, item["url"], product)
        print(f"[ok] {product['price']:>7.2f}  stock {product['stock']:>2}  {product['title']}")
        time.sleep(REQUEST_DELAY_SECONDS)

    conn.commit()
    write_reports(conn, alerts)
    conn.close()

    print(f"\nChecked {len(watchlist)} products, {len(alerts)} alerts.")
    for _, title, event, detail, _ in alerts:
        print(f"  {event:<15} {detail:<28} {title}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default=HERE / "watchlist.csv", type=Path)
    run(parser.parse_args().watchlist)
