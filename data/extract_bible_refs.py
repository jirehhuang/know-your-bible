import json
import re
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.utils.bible import BIBLE
from app.main import match_book_name

def load_sermon_urls(filepath="data/sermon_urls.txt"):
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]

def load_existing_data(filepath="data/sermon_refs.json"):
    if Path(filepath).exists():
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {entry["url"]: entry for entry in data}
            except json.JSONDecodeError:
                print("[Warning] Could not decode JSON. Starting fresh.")
                return {}
    return {}

def extract_bible_refs_from_sermon(url, page):
    try:
        page.goto(url, timeout=120000)
        page.wait_for_selector(".rtBibleRef", timeout=120000)  # <-- wait for dynamic refs

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        refs = []
        for a in soup.find_all("a", class_="rtBibleRef"):
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

        return refs

    except Exception as e:
        print(f"[Error] extract_bible_refs_from_sermon() failed on {url}: {e}")
        return []

def process_all_sermons(input_file="data/sermon_urls.txt", output_file="data/sermon_refs.json"):
    sermon_data = []
    urls = load_sermon_urls(input_file)
    existing_data = load_existing_data(output_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(120000)

        for idx, url in enumerate(urls, 1):
            if url in existing_data and existing_data[url].get("references"):
                print(f"[{idx}/{len(urls)}] Skipping cached: {url}")
                sermon_data.append(existing_data[url])
                continue

            try:
                print(f"[{idx}/{len(urls)}] Processing: {url}")
                refs = extract_bible_refs_from_sermon(url, page)
                sermon_data.append({
                    "url": url,
                    "references": refs
                })
                time.sleep(0.2)  # Be gentle to the server
            except Exception as e:
                print(f"[Fatal Error] Failed on {url}: {e}")
                sermon_data.append({
                    "url": url,
                    "references": [],
                    "error": str(e)
                })

        browser.close()

    ## Save merged data to JSON
    all_urls = {entry["url"]: entry for entry in sermon_data + list(existing_data.values())}
    merged_data = list(all_urls.values())

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=2)

    print(f"\n✅ Done. Saved to {output_file}")

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

def get_all_references(input_file="data/sermon_refs.json"):
    ## Load original references
    with open(input_file, "r", encoding="utf-8") as f:
        sermon_refs = json.load(f)

    ## Gather all references
    all_refs_raw = []
    for entry in sermon_refs:
        all_refs_raw.extend(entry.get("references", []))

    ## Normalize and expand
    all_refs_clean = normalize_and_expand_references(all_refs_raw)

    ## Save to new JSON file
    output_path = Path("data/sermon_refs_list.json")
    output_path.write_text(json.dumps(all_refs_clean, indent=2), encoding="utf-8")

    return all_refs_clean

## Execute
process_all_sermons()
all_references = get_all_references()