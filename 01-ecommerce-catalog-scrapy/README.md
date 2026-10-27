# E-commerce Catalog Crawler (Scrapy)

Crawls an entire online store and turns it into a clean, client-ready dataset and Excel report.

**Result:** 1,000 products across 50 categories in about 65 seconds, with zero missing prices, ratings or stock values.

## What it does
- Starts at the homepage, discovers all 50 categories, and follows pagination in each one
- Visits every product page and extracts: title, category, price, star rating (converted to 1–5),
  units in stock (parsed from "In stock (22 available)"), review count, UPC, description, image URL, product URL
- Cleans and types the data (prices as numbers, site truncation markers removed, duplicates dropped by UPC)
- Crawls politely: respects robots.txt, auto-throttles to the server, retries failed requests
- Builds an Excel report with:
  - **Summary**: headline numbers
  - **Products**: full dataset with filters and a frozen header
  - **By Category**: counts, average price and rating, total stock, plus a bar chart
  - **Low Stock**: items with 3 or fewer units left
  - **Top Rated Value**: 5-star items sorted by price

## Run
```bash
python catalog_spider.py   # crawl -> output/products.csv, output/products.json
python build_report.py     # report -> output/catalog_report.xlsx
```

## Adapting it for a client
The same structure (category discovery → paginated listings → detail pages → report) fits most
e-commerce, directory, real-estate and job-board sites. Usually only the CSS selectors in
`parse_listing` and `parse_product` need to change.
