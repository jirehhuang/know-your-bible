import json
import re
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.utils.bible import BIBLE
from app.main import match_book_name

def load_gty_resource_urls(filepath="data/resource_urls.txt"):
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip() and "gty.org" in line]

def load_existing_data(filepath="data/biblerefs/sermon_biblerefs.json"):
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {entry["url"]: entry for entry in data}
            except json.JSONDecodeError:
                print("[Warning] Could not decode JSON. Starting fresh.")
                return {}
    return {}

def save_checkpoint(data_dict, path):
    merged = list(data_dict.values())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"[Checkpoint] Saved {len(merged)} records to {path}")

def extract_biblerefs_from_sermon(url, page):
    try:
        page.goto(url, timeout=30000)
        page.wait_for_selector(".rtBibleRef", timeout=30000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        refs = []

        # Restrict to within the main content area
        main = soup.find("main", class_="col s12 l9 an-asset page-content")
        if main:
            for a in main.find_all("a", class_="rtBibleRef"):
                data_ref = a.get("data-reference")
                if data_ref:
                    normalized = (
                        data_ref
                        .replace(".", ":")
                        .replace("–", "-")
                        .replace("—", "-")
                        .strip()
                    )
                    refs.append(normalized)
        else:
            print(f"[Warning] <main class='col s12 l9 an-asset page-content'> not found on {url}")

        return refs

    except Exception as e:
        print(f"[Error] extract_biblerefs_from_sermon() failed on {url}: {e}")
        return []
    
## Manually confirmed to have no references
skip_urls = [
    "https://www.gty.org/library/sermons-library/70-58/thinking-biblically-about-current-events-a-conversation-with-john-macarthur",
]

def process_all_sermons(input_file="data/resource_urls.txt", output_file="data/biblerefs/sermon_biblerefs.json", checkpoint_every=10):
    urls = load_gty_resource_urls(input_file)
    existing_data = load_existing_data(output_file)
    new_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)

        for idx, url in enumerate(urls, 1):
            if url in skip_urls:
                print(f"[{idx}/{len(urls)}] Skipping known no-ref URL: {url}")
                continue

            if url in existing_data and isinstance(existing_data[url].get("references", None), list):
                print(f"[{idx}/{len(urls)}] Skipping cached: {url}")
                new_data[url] = existing_data[url]
                continue

            try:
                print(f"[{idx}/{len(urls)}] Processing: {url}")
                refs = extract_biblerefs_from_sermon(url, page)
                new_data[url] = {
                    "url": url,
                    "references": refs
                }
                time.sleep(0.2)
            except Exception as e:
                print(f"[Fatal Error] Failed on {url}: {e}")
                new_data[url] = {
                    "url": url,
                    "references": [],
                    "error": str(e)
                }

            ## Save checkpoint every N iterations
            if idx % checkpoint_every == 0:
                all_data = {**existing_data, **new_data}
                save_checkpoint(all_data, output_file)

        browser.close()

    ## Final save
    all_data = {**existing_data, **new_data}
    save_checkpoint(all_data, output_file)
    print(f"\n✅ Done. Final data saved to {output_file}")

def expand_reference(book, chapter, verse_range):
    verses = []
    if '-' in verse_range:
        start, end = map(int, verse_range.split('-'))
        verses = [f"{book} {chapter}:{v}" for v in range(start, end + 1)]
    else:
        verses = [f"{book} {chapter}:{verse_range}"]
    return verses

def normalize_and_expand_references(reference_list):
    expanded = []
    for ref in reference_list:
        clean = ref.replace('\u2013', '-').replace('\u2014', '-').replace('–', '-').replace('—', '-')
        match = re.match(r"([1-3]?\s?[A-Za-z]+)\s+(\d+):([\d\-]+)", clean)
        if match:
            book_abbr = match.group(1).strip()
            chapter = match.group(2)
            verse_part = match.group(3)
            book_full = match_book_name(book_abbr)
            if book_full:
                expanded.extend(expand_reference(book_full, chapter, verse_part))
    return expanded

def get_all_references(input_file="data/biblerefs/sermon_biblerefs.json"):
    ## Load original references
    with open(input_file, "r", encoding="utf-8") as f:
        biblerefs = json.load(f)

    ## Gather all references
    all_refs_raw = []
    for entry in biblerefs:
        all_refs_raw.extend(entry.get("references", []))

    ## Normalize and expand
    all_refs_clean = normalize_and_expand_references(all_refs_raw)

    ## Save to new JSON file
    output_path = Path("data/biblerefs/biblerefs.txt")
    output_path.write_text("\n".join(all_refs_clean), encoding="utf-8")

    return all_refs_clean

## Execute
process_all_sermons()
all_references = get_all_references()
