# Python Web Scraping Portfolio

Three working scrapers, each covering a different kind of job clients post on Upwork.
All target public sandbox sites built for scraping practice
([books.toscrape.com](https://books.toscrape.com), [quotes.toscrape.com](https://quotes.toscrape.com)),
so the code and output can be shown publicly.

| Project | What it shows | Stack | Output |
|---|---|---|---|
| [01 – E-commerce catalog crawler](01-ecommerce-catalog-scrapy/) | Full-site crawl: 50 categories, pagination, 1,000 product pages, typed/cleaned fields, Excel report with chart | Scrapy, pandas, openpyxl | CSV, JSON, formatted XLSX |
| [02 – Login + infinite scroll](02-login-infinite-scroll-playwright/) | JavaScript-loaded content, form login with CSRF token, members-only data, merging two sources | Playwright, pandas | CSV, XLSX |
| [03 – Price & stock monitor](03-price-monitor/) | Scheduled monitoring, SQLite history, change detection and alerts, unit tests | requests, BeautifulSoup, SQLite | SQLite DB, alerts CSV, XLSX report |

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Each project folder has its own README with run instructions.
