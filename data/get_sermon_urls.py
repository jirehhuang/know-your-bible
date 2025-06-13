from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

def get_gty_sermon_urls_for_year(year):
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
                page.wait_for_load_state('networkidle')  # wait for JS to load

                soup = BeautifulSoup(page.content(), 'html.parser')
                sermon_divs = soup.find_all("div", class_="gty-asset store-library sermon")

                if not sermon_divs:
                    print(f"No sermons found on page {page_num} for year {year}. Stopping.")
                    break  # No more pages

                for div in sermon_divs:
                    a_tag = div.find("a", href=True)
                    if a_tag:
                        full_url = urljoin(base_url, a_tag['href'])
                        all_urls.append(full_url)

                page_num += 1
                time.sleep(0.2)  # Be polite to the server

            except Exception as e:
                print(f"[Error] Failed to process page {page_num} for year {year}: {e}")
                break  # Break on failure to avoid infinite loops

        browser.close()

    return all_urls

def get_gty_sermon_urls(start_year=2024, end_year=1969):
    gty_sermon_urls = []

    for year in range(start_year, end_year - 1, -1):  # Count down from 2024 to 1969
        print(f"\n=== Processing year {year} ===")
        try:
            year_urls = get_gty_sermon_urls_for_year(year)
            print(f"Found {len(year_urls)} sermons in {year}")
            gty_sermon_urls.extend(year_urls)
        except Exception as e:
            print(f"[Error] Skipping year {year} due to error: {e}")
            continue  # Move on to the next year

    return gty_sermon_urls

## Run it
gty_links = get_gty_sermon_urls()

## Optional: Save to a file
with open("data/sermon_urls.txt", "w") as f:
    for link in gty_links:
        f.write(link + "\n")

print(f"\nTotal sermons from gty.org collected: {len(gty_links)}")
