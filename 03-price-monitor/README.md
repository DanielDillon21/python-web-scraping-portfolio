# Price & Stock Monitor

Tracks a list of product pages over time and alerts on changes: price drops, price increases,
price at or below a target, sold out, back in stock, and low stock.

## What it does
- Reads `watchlist.csv` (product URL plus an optional target price)
- Fetches each page with retries and backoff, then parses price and stock
- Stores every check in a local **SQLite** database so history builds up across runs
- Compares each check with the previous one and raises alerts
- Writes `output/alerts.csv` and `output/price_report.xlsx` with three sheets:
  - **Latest Prices**: includes lowest and highest price seen
  - **Alerts**
  - **History**
- Includes **unit tests** that use saved HTML, so the alert logic is verified even when live prices don't move

## Run
```bash
python price_monitor.py           # check everything in watchlist.csv
python -m unittest -v             # 9 tests
```

## Schedule it (Windows)
```bash
schtasks /create /tn "PriceMonitor" /sc daily /st 09:00 /tr "python C:\path\to\price_monitor.py"
```
On Linux/macOS, use cron: `0 9 * * * python /path/to/price_monitor.py`

## Adapting it for a client
Swap the selectors in `parse_product` for the target store. Alerts can be emailed, posted to
Slack/Discord, or pushed to Google Sheets. That's about a 20-line addition to `run()`.
