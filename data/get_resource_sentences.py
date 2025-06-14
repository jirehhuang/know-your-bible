import os
import sys
import json
import re
import nltk
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from get_resource_urls import url_to_filename

## Adjust path to import BIBLE
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.utils.bible import BIBLE

## Setup
nltk.download("punkt", quiet=True)
from nltk.tokenize import sent_tokenize

## Constants
BIBLE_BOOKS = set(BIBLE.keys())
TEMP_URL_DIR = 'data/temp_url'
RESOURCE_JSON = 'data/resources.json'

os.makedirs(TEMP_URL_DIR, exist_ok=True)

## Utilities
def ensure_dirs():
    os.makedirs(TEMP_URL_DIR, exist_ok=True)

def contains_bible_book(sentence: str) -> bool:
    return any(book in sentence for book in BIBLE_BOOKS)


def download_and_save_article(url: str, domain: str) -> str:
    """
    Download and save article HTML depending on domain logic.
    - DG requires headful mode
    - GTY uses networkidle wait in headless
    """
    html_path = os.path.join(TEMP_URL_DIR, f"{url_to_filename(url)}.html")

    if os.path.exists(html_path):
        print(f"[DEBUG] Using cached file {html_path}")
        return html_path

    with sync_playwright() as p:
        headless = not ("desiringgod.org" in domain)
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        print(f"[DEBUG] Visiting {url} ({'headless' if headless else 'headful'})")
        page.goto(url, timeout=60000)

        html = page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"[DEBUG] Saved HTML to {html_path}")
        browser.close()

    return html_path

def normalize_text(text: str) -> str:
    text = re.sub(r"[–—−‒―]", "-", text)
    text = re.sub(r"[\n\r\t]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_paragraphs_from_dg(html_path: str) -> str:
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    body = soup.select_one("div.resource__body")
    if not body:
        return ""

    paragraphs = []
    for p in body.find_all('p'):
        text_parts = [t.get_text(" ", strip=True) for t in p.contents if hasattr(t, 'get_text')]
        paragraph_text = normalize_text(" ".join(text_parts))
        paragraphs.append(paragraph_text)

    return " ".join(paragraphs)

def extract_paragraphs_from_gty(html_path: str) -> str:
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    body = soup.find("div", attrs={"data-swiftype-name": "body", "data-swiftype-type": "text"})
    if not body:
        return ""

    paragraphs = []
    for p in body.find_all('p'):
        text_parts = [t.get_text(" ", strip=True) for t in p.contents if hasattr(t, 'get_text')]
        paragraph_text = normalize_text(" ".join(text_parts))
        paragraphs.append(paragraph_text)

    return " ".join(paragraphs)

def process_all_resources():
    ensure_dirs()

    if not os.path.exists(RESOURCE_JSON):
        print(f"[ERROR] File not found: {RESOURCE_JSON}")
        return

    with open(RESOURCE_JSON, 'r', encoding='utf-8') as f:
        resources = json.load(f)

    for idx, (url, meta) in enumerate(sorted(resources.items()), 1):
        if 'sentences' in meta:
            print(f"[{idx}] Skipping already-processed: {url}")
            continue

        print(f"[{idx}] Processing: {url}")

        if "www.desiringgod.org/labs" in url:
            print(f"[DEBUG] Skipping labs resource: {url}")
            resources[url]['sentences'] = []
            continue

        try:
            domain = urlparse(url).netloc
            html_path = download_and_save_article(url, domain)

            if 'desiringgod.org' in domain:
                article_text = extract_paragraphs_from_dg(html_path)
            elif 'gty.org' in domain:
                article_text = extract_paragraphs_from_gty(html_path)
            else:
                print(f"[ERROR] Unsupported domain: {domain}")
                resources[url]['sentences'] = None
                continue

            sentences = sent_tokenize(article_text)
            bible_sentences = [s.strip() for s in sentences if contains_bible_book(s)]
            resources[url]['sentences'] = sorted(bible_sentences)

            print(f"[DEBUG] Added {len(bible_sentences)} sentence(s) from {url}")

        except Exception as e:
            print(f"❌ Error processing {url}: {e}")
            resources[url]['sentences'] = None

        with open(RESOURCE_JSON, 'w', encoding='utf-8') as f:
            json.dump(resources, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    process_all_resources()
