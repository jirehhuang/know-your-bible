import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright



##==================================================
## gty.org
##==================================================

## File where GTY sermon URLs will be saved
SERMON_URLS_TXT = "data/resource_urls.txt"

## Ensure the data directory exists
os.makedirs("data", exist_ok=True)

def load_existing_sermon_urls():
    """
    Load previously saved sermon URLs to avoid duplicates.
    
    Returns:
        A set of previously saved sermon URLs.
    """
    if os.path.exists(SERMON_URLS_TXT):
        with open(SERMON_URLS_TXT, encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def append_sermon_urls(new_urls, existing_urls):
    """
    Append new URLs to the sermon URL file if they are not duplicates.
    
    Args:
        new_urls (list of str): Newly scraped URLs.
        existing_urls (set of str): Already saved URLs.
    
    Returns:
        int: Number of new URLs actually written to file.
    """
    unique_new_urls = [url for url in new_urls if url not in existing_urls]
    if unique_new_urls:
        with open(SERMON_URLS_TXT, "a", encoding="utf-8") as f:
            for url in unique_new_urls:
                f.write(url + "\n")
        existing_urls.update(unique_new_urls)
    return len(unique_new_urls)

def get_gty_sermon_urls_for_year(year):
    """
    Scrapes GTY sermon URLs for a given year across all paginated archive pages.
    
    Args:
        year (int): The year to scrape sermons for.
    
    Returns:
        List of full sermon URLs.
    """
    base_url = "https://www.gty.org"
    archive_base = f"{base_url}/library/resources/sermons-library/date/{{page}}?year={year}"
    all_urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(120000)  # 2 minutes timeout

        page_num = 1
        while True:
            archive_url = archive_base.format(page=page_num)
            print(f"Fetching: {archive_url}")

            try:
                page.goto(archive_url)
                page.wait_for_load_state('networkidle')

                soup = BeautifulSoup(page.content(), 'html.parser')
                sermon_divs = soup.find_all("div", class_="gty-asset store-library sermon")

                if not sermon_divs:
                    print(f"No sermons found on page {page_num} for year {year}. Stopping.")
                    break

                for div in sermon_divs:
                    a_tag = div.find("a", href=True)
                    if a_tag:
                        full_url = urljoin(base_url, a_tag['href'])
                        all_urls.append(full_url)

                page_num += 1
                time.sleep(0.2)  # polite delay

            except Exception as e:
                print(f"[Error] Failed to process page {page_num} for year {year}: {e}")
                break

        browser.close()

    return all_urls

def get_gty_sermon_urls(start_year=2025, end_year=1969):
    """
    Crawls GTY sermon archives for each year in the given range and updates the URL list.
    
    Args:
        start_year (int): Most recent year to scrape.
        end_year (int): Earliest year to scrape.
    
    Returns:
        set: Full set of all collected sermon URLs (existing + new).
    """
    existing_urls = load_existing_sermon_urls()

    for year in range(start_year, end_year - 1, -1):
        print(f"\n=== Processing year {year} ===")
        try:
            year_urls = get_gty_sermon_urls_for_year(year)
            num_added = append_sermon_urls(year_urls, existing_urls)
            print(f"Found {len(year_urls)} sermons, {num_added} new URLs added.")
        except Exception as e:
            print(f"[Error] Skipping year {year} due to error: {e}")
            continue

    return existing_urls

## Execute the GTY sermon scraper
if __name__ == "__main__":
    all_gty_urls = get_gty_sermon_urls()
    print(f"\n✅ Total unique sermons collected from gty.org: {len(all_gty_urls)}")



##==================================================
## desiringgod.org
##==================================================

import json
from datetime import datetime

DG_URL = "https://www.desiringgod.org"
START_YEAR = datetime.now().year
END_YEAR = 1970

RESOURCES_JSON = "data/resources_dg.json"
URLS_TXT = "data/resource_urls.txt"
DATA_DIR = "data/desiringgod"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_existing_data():
    """
    Loads existing resources and URLs.
    Assumes resources.json is a dict keyed by URL.
    """
    resources = {}
    seen_urls = set()

    if os.path.exists(RESOURCES_JSON):
        with open(RESOURCES_JSON, encoding="utf-8") as f:
            resources = json.load(f)
            seen_urls = set(resources.keys())

    if os.path.exists(URLS_TXT):
        with open(URLS_TXT, encoding="utf-8") as f:
            urls = set(line.strip() for line in f if line.strip())
    else:
        urls = seen_urls.copy()

    return resources, urls

def save_data(resources, urls):
    """
    Save resources (as dict keyed by URL) and URL list to disk.
    """
    with open(RESOURCES_JSON, "w", encoding="utf-8") as f:
        json.dump(resources, f, indent=2, ensure_ascii=False)

    with open(URLS_TXT, "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(url + "\n")

def save_and_parse_dg_year_page(year=2000, page=1, overwrite=False):
    """
    Load and parse DesiringGod articles for a specific year and page.
    """
    filename = f"{DATA_DIR}/desiringgod_{year}_{page}.html"

    if not overwrite and os.path.exists(filename):
        print(f"[DEBUG] Using cached file {filename}")
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page_obj = browser.new_page()
            url = f"{DG_URL}/dates/{year}?page={page}"
            print(f"[DEBUG] Visiting {url}")
            page_obj.goto(url, timeout=60000)
            html = page_obj.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[DEBUG] Saved HTML to {filename}")
            browser.close()

    with open(filename, encoding="utf-8") as f:
        saved_html = f.read()

    soup = BeautifulSoup(saved_html, "html.parser")
    main = soup.select_one("main.page-content") or soup

    results = {}
    cards = main.select("a.card__shadow")
    print(f"[DEBUG] Found {len(cards)} article cards on year={year} page={page}")

    for idx, card in enumerate(cards):
        article_url = urljoin(DG_URL, card.get("href", ""))
        author_tag = card.select_one("span.card__author-text")
        author = author_tag.get_text(strip=True) if author_tag else None
        scripture_tag = card.select_one("div.card--resource__scripture")
        scripture = scripture_tag.get_text(strip=True).replace("Scripture: ", "").replace("Scripture:", "") if scripture_tag else None
        date_tag = card.select_one("time.resource__date")
        date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else None

        print(f"[DEBUG] Card {idx+1}: url={article_url}, author={author}, scripture={scripture}, date={date}")

        results[article_url] = {
            "author": author,
            "scripture": scripture,
            "date": date,
        }

    print(f"[DEBUG] Returning {len(results)} articles for year={year} page={page}")
    return results

def get_dg_resource_urls(overwrite=False):
    """
    Crawl DesiringGod archives and extract article metadata.
    """
    resources, urls = load_existing_data()

    for year in range(START_YEAR, END_YEAR - 1, -1):
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

            new_articles = {url: data for url, data in articles.items() if url not in urls}

            if not new_articles:
                print(f"No new articles out of {len(articles)} on year {year} page {page_num}, skipping further pages for this year.")
                break

            urls.update(new_articles.keys())
            resources.update(new_articles)
            save_data(resources, urls)

            print(f"Year {year} page {page_num}: Found {len(new_articles)} new articles out of {len(articles)}.")
            page_num += 1

if __name__ == "__main__":
    get_dg_resource_urls(overwrite=False)
    print(f"\n✅ Total unique resources collected from desiringgod.org: {len(load_existing_data()[0])}")
