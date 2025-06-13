import os
import sys
import json
import nltk
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

## Adjust path to import BIBLE
sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.utils.bible import BIBLE

## Download NLTK tokenizer
nltk.download("punkt", quiet=True)
from nltk.tokenize import sent_tokenize

## Constants
BIBLE_BOOKS = set(BIBLE.keys())
TEMP_HTML = 'data/biblementions/desiringgod_temp.html'
OUTPUT_JSON = 'data/biblementions/sentences.json'

def ensure_dirs():
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

def load_sentences_json() -> list:
    if not os.path.exists(OUTPUT_JSON):
        return []
    with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_sentences_json(data: list):
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def url_already_processed(data: list, url: str) -> bool:
    return any(entry['url'] == url for entry in data)

def download_and_save_dg_article(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Headful mode required for desiringgod.org
        page = browser.new_page()

        print(f"Visiting {url}")
        page.goto(url, timeout=60000)

        html = page.content()
        with open(TEMP_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        browser.close()
    return TEMP_HTML

def extract_article_text(html_path: str) -> str:
    """
    Extracts and returns clean paragraph-level text from the article HTML.
    It collects text from <p> and <a> inside <div class="resource__body">,
    and removes line breaks within those elements.
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    body = soup.select_one("div.resource__body")
    if not body:
        return ""

    texts = []

    # Extract from <p> and <a> inside resource__body
    for tag in body.find_all(['p']):
        text = tag.get_text(separator=" ", strip=True)
        text = ' '.join(text.split())  # Remove all extra whitespace and line breaks
        if text:
            texts.append(text)

    print(texts)

    return ' '.join(texts)

def contains_bible_book(sentence: str) -> bool:
    return any(book in sentence for book in BIBLE_BOOKS)

def process_desiringgod_article(url: str):
    """
    Scrapes a DesiringGod article, extracts Bible-referencing sentences,
    and saves results to sentences.json in structured format.
    """
    ensure_dirs()
    existing_data = load_sentences_json()

    if url_already_processed(existing_data, url):
        print(f"URL already processed: {url}")
        return

    html_path = download_and_save_dg_article(url)
    full_text = extract_article_text(html_path)
    all_sentences = sent_tokenize(full_text)
    bible_sentences = [s.strip() for s in all_sentences if contains_bible_book(s)]

    if bible_sentences:
        existing_data.append({
            "url": url,
            "sentences": sorted(bible_sentences)
        })
        save_sentences_json(existing_data)
        print(f"Added {len(bible_sentences)} sentences from {url}")
    else:
        print(f"No Bible references found in {url}")

# Example usage
if __name__ == "__main__":
    test_url = "https://www.desiringgod.org/articles/bring-the-bible-home-to-your-heart"
    process_desiringgod_article(test_url)
