"""
Full-catalog e-commerce crawler built with Scrapy.

Crawls every category and product page on books.toscrape.com (a public
sandbox built for scraping practice), follows pagination, and extracts
clean, typed product data: title, category, price, star rating, stock
count, UPC, description, image URL and product URL.

Run:
    python catalog_spider.py
Outputs:
    output/products.csv
    output/products.json
"""

import re
from pathlib import Path

import scrapy
from scrapy.crawler import CrawlerProcess

OUTPUT_DIR = Path(__file__).parent / "output"

RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class CatalogSpider(scrapy.Spider):
    name = "catalog"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]

    def parse(self, response):
        """Homepage: fan out to every category listing."""
        for link in response.css("div.side_categories ul li ul li a"):
            yield response.follow(
                link,
                callback=self.parse_listing,
                cb_kwargs={"category": link.css("::text").get().strip()},
            )

    def parse_listing(self, response, category):
        """Category listing: queue each product, then follow pagination."""
        for href in response.css("article.product_pod h3 a::attr(href)").getall():
            yield response.follow(
                href, callback=self.parse_product, cb_kwargs={"category": category}
            )

        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(
                next_page, callback=self.parse_listing, cb_kwargs={"category": category}
            )

    def parse_product(self, response, category):
        table = {
            row.css("th::text").get(): row.css("td::text").get()
            for row in response.css("table.table-striped tr")
        }

        rating_class = response.css("p.star-rating::attr(class)").get(default="")
        rating_word = rating_class.replace("star-rating", "").strip()

        stock_match = re.search(r"\((\d+) available\)", table.get("Availability", ""))

        yield {
            "title": response.css("div.product_main h1::text").get(),
            "category": category,
            "price_gbp": parse_money(table.get("Price (incl. tax)")),
            "rating": RATINGS.get(rating_word),
            "in_stock": int(stock_match.group(1)) if stock_match else 0,
            "num_reviews": int(table.get("Number of reviews", 0)),
            "upc": table.get("UPC"),
            "description": clean_description(response.css("#product_description + p::text").get()),
            "image_url": response.urljoin(response.css("div.item img::attr(src)").get()),
            "url": response.url,
        }


def parse_money(text):
    """'£51.77' -> 51.77. Returns None for missing values instead of crashing."""
    if not text:
        return None
    return float(re.sub(r"[^\d.]", "", text))


def clean_description(text):
    """Strip whitespace and the site's truncation marker ('...more')."""
    if not text:
        return ""
    return re.sub(r"\s*\.\.\.more$", "", text.strip())


def run():
    OUTPUT_DIR.mkdir(exist_ok=True)
    process = CrawlerProcess(
        settings={
            "FEEDS": {
                str(OUTPUT_DIR / "products.csv"): {"format": "csv", "encoding": "utf-8-sig", "overwrite": True},
                str(OUTPUT_DIR / "products.json"): {"format": "json", "encoding": "utf-8", "indent": 2, "overwrite": True},
            },
            # Polite crawling: identify ourselves, respect robots.txt, adapt speed to the server.
            "USER_AGENT": "portfolio-catalog-crawler (+https://www.upwork.com/freelancers/~0181ce0b02be19129c)",
            "ROBOTSTXT_OBEY": True,
            "AUTOTHROTTLE_ENABLED": True,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
            "RETRY_TIMES": 3,
            "HTTPCACHE_ENABLED": False,
            "LOG_LEVEL": "INFO",
        }
    )
    process.crawl(CatalogSpider)
    process.start()


if __name__ == "__main__":
    run()
