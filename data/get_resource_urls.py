import os
import json
import time
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

#==================================================
# Constants and Setup
#==================================================

DG_URL = "https://www.desiringgod.org"
GTY_URL = "https://www.gty.org"
START_YEAR = datetime.now().year
END_YEAR = 1969
RESOURCES_JSON = "data/resources.json"
DATA_DIR = "data/temp_year_page"

os.makedirs("data", exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

#==================================================
# Utilities
#==================================================

def load_existing_resources():
    if os.path.exists(RESOURCES_JSON):
        with open(RESOURCES_JSON, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_resources(resources):
    with open(RESOURCES_JSON, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(resources.items())), f, indent=2, ensure_ascii=False)

def url_to_filename(url):
    parsed = urlparse(url)
    base = parsed.netloc + parsed.path + ('?' + parsed.query if parsed.query else '')
    filename = re.sub(r'[<>:"/\\|?*\s]+', '_', base)
    return filename[:255]

#==================================================
# Shared Scraper Handler
#==================================================

def save_and_parse_year_page(site, year=2000, page=1, overwrite=False):
    if site == 'dg':
        base_url = f"{DG_URL}/dates/{year}?page={page}"
    elif site == 'gty':
        base_url = f"{GTY_URL}/library/resources/sermons-library/date/{page}?year={year}"
    else:
        raise ValueError("Unsupported site")

    filename = os.path.join(DATA_DIR, f"{url_to_filename(base_url)}.html")

    if not overwrite and os.path.exists(filename):
        print(f"[DEBUG] Using cached file {filename}")
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page_obj = browser.new_page()
            print(f"[DEBUG] Visiting {base_url}")
            page_obj.goto(base_url, timeout=60000)
            html = page_obj.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[DEBUG] Saved HTML to {filename}")
            browser.close()

    with open(filename, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    results = {}
    if site == 'dg':
        main = soup.select_one("main.page-content") or soup
        cards = main.select("a.card__shadow")
        print(f"[DEBUG] Found {len(cards)} DG article cards on year={year} page={page}")

        for idx, card in enumerate(cards):
            article_url = urljoin(DG_URL, card.get("href", ""))
            author_tag = card.select_one("span.card__author-text")
            author = author_tag.get_text(strip=True) if author_tag else None

            scripture_tag = card.select_one("div.card--resource__scripture")
            scripture = scripture_tag.get_text(strip=True).replace("Scripture: ", "").replace("Scripture:", "") if scripture_tag else None

            date_tag = card.select_one("div.card--resource__date")
            date = date_tag.get_text(strip=True) if date_tag else None

            print(f"[DEBUG] DG {idx+1}: url={article_url}, author={author}, scripture={scripture}, date={date}")
            results[article_url] = {
                "author": author,
                "scripture": scripture,
                "date": date,
            }
    elif site == 'gty':
        main = soup.select_one("main") or soup
        titles = main.select("div.title a")
        print(f"[DEBUG] Found {len(titles)} GTY sermon entries on year={year} page={page}")

        for idx, a in enumerate(titles):
            article_url = urljoin(GTY_URL, a.get("href", ""))
            container = a.find_parent("div", class_="title").find_parent("div")
            scripture_tag = container.select_one("span[data-bind*=scripture]")
            date_tag = container.select_one("span[data-bind*=dateDisplay]")
            author = "John MacArthur"
            
            scripture = scripture_tag.get_text(strip=True) if scripture_tag else None
            date = date_tag.get_text(strip=True) if date_tag else None

            print(f"[DEBUG] GTY {idx+1}: url={article_url}, author={author}, scripture={scripture}, date={date}")
            results[article_url] = {
                "author": author,
                "scripture": scripture,
                "date": date,
            }

    return results

#==================================================
# Site Resource Collectors
#==================================================

def get_site_resources(site, overwrite=False):
    resources = load_existing_resources()

    for year in range(START_YEAR if site == "dg" else min(START_YEAR, 2024), END_YEAR - 1, -1):
        print(f"\n--- Processing {site.upper()} year {year} ---")
        page_num = 1
        while True:
            try:
                articles = save_and_parse_year_page(site, year, page_num, overwrite)
            except Exception as e:
                print(f"[ERROR] {site.upper()} {year} page {page_num}: {e}")
                break

            if not articles:
                break

            new_articles = {k: v for k, v in articles.items() if k not in resources}
            if not new_articles:
                break

            resources.update(new_articles)
            save_resources(resources)
            print(f"[DEBUG] Saved {len(new_articles)} {site.upper()} articles.")

            page_num += 1

#==================================================
# Main
#==================================================

if __name__ == "__main__":
    get_site_resources('dg', overwrite=False)
    get_site_resources('gty', overwrite=False)
    all_resources = load_existing_resources()
    print(f"\n✅ Total unified resources collected: {len(all_resources)}")
