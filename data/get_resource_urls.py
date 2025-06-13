import os
import json
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

##==================================================
## desiringgod.org
##==================================================

DG_URL = "https://www.desiringgod.org"
START_YEAR = 1970
END_YEAR = datetime.now().year

RESOURCES_JSON = "data/resources_dg.json"
URLS_TXT = "data/resource_urls.txt"

DATA_DIR = "data/desiringgod"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_existing_data():
    resources = []
    seen_urls = set()

    if os.path.exists(RESOURCES_JSON):
        with open(RESOURCES_JSON, encoding="utf-8") as f:
            for r in json.load(f):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    resources.append(r)

    if os.path.exists(URLS_TXT):
        with open(URLS_TXT, encoding="utf-8") as f:
            urls = set(line.strip() for line in f if line.strip())
    else:
        urls = seen_urls.copy()  # derive from cleaned resources if missing

    return resources, urls

def save_data(resources, urls):
    """
    Save resources and URLs to disk.
    """
    with open(RESOURCES_JSON, "w", encoding="utf-8") as f:
        json.dump(resources, f, indent=2, ensure_ascii=False)

    with open(URLS_TXT, "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(url + "\n")

def save_and_parse_dg_year_page(year=2000, page=1, overwrite=False):
    """
    Load and parse DesiringGod articles for a specific year and page.
    Saves HTML to disk and reuses cached file unless overwrite is True.

    Args:
        year (int): Year to scrape.
        page (int): Page number.
        overwrite (bool): If False, uses cached HTML if available.

    Returns:
        List of article metadata dicts.
    """
    filename = f"{DATA_DIR}/desiringgod_{year}_{page}.html"

    # Skip downloading if the file exists and overwrite=False
    if not overwrite and os.path.exists(filename):
        print(f"Using cached file {filename}")
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Headful mode for debugging
            page_obj = browser.new_page()

            url = f"{DG_URL}/dates/{year}?page={page}"
            print(f"Visiting {url}")
            page_obj.goto(url, timeout=60000)

            # Save full HTML content
            html = page_obj.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)

            browser.close()

    # Parse saved HTML file
    with open(filename, encoding="utf-8") as f:
        saved_html = f.read()

    soup = BeautifulSoup(saved_html, "html.parser")

    main = soup.select_one("main.page-content") or soup

    results = []
    for card in main.select("a.card__shadow"):
        article_url = urljoin(DG_URL, card.get("href", ""))

        ## Extract author
        author_tag = card.select_one("span.card__author-text")
        author = author_tag.get_text(strip=True) if author_tag else None

        ## Extract scripture reference
        scripture_tag = card.select_one("div.card--resource__scripture")
        scripture = scripture_tag.get_text(strip=True).replace("Scripture: ", "").replace("Scripture:", "") if scripture_tag else None

        ## Extract date
        date_tag = card.select_one("time.resource__date")
        date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else None

        results.append({
            "url": article_url,
            "author": author,
            "scripture": scripture,
            "date": date
        })

    return results

def get_dg_resource_urls(overwrite=False):
    """
    Crawl DesiringGod archives and extract article metadata.
    Skips previously seen URLs and avoids duplicated resources.

    Args:
        overwrite (bool): If True, re-fetch HTML pages even if cached files exist.
    """
    resources, urls = load_existing_data()

    for year in range(END_YEAR, START_YEAR - 1, -1):
        print(f"\n--- Processing year {year} ---")
        page_num = 1
        while True:
            try:
                articles = save_and_parse_dg_year_page(year, page_num, overwrite=overwrite)
            except Exception as e:
                print(f"Error loading {year} page {page_num}: {e}")
                break

            if not articles:
                print(f"No articles found for year {year} page {page_num}, moving to next year.")
                break

            new_articles = []
            for art in articles:
                if art["url"] not in urls:
                    urls.add(art["url"])
                    new_articles.append(art)

            if not new_articles:
                print(f"No new articles on year {year} page {page_num}, skipping further pages for this year.")
                break

            resources.extend(new_articles)
            save_data(resources, urls)

            print(f"Year {year} page {page_num}: Found {len(new_articles)} new articles.")

            page_num += 1

if __name__ == "__main__":
    # Set overwrite=True to refresh cached HTML files
    get_dg_resource_urls(overwrite=False)
