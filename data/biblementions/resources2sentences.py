import os
import sys
import json
import re
import nltk
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# Adjust path to import BIBLE
sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.utils.bible import BIBLE

# Setup
nltk.download("punkt", quiet=True)
from nltk.tokenize import sent_tokenize

# Constants
BIBLE_BOOKS = set(BIBLE.keys())
TEMP_HTML = 'data/biblementions/temp.html'
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

def contains_bible_book(sentence: str) -> bool:
    return any(book in sentence for book in BIBLE_BOOKS)

def download_and_save_article(url: str, domain: str) -> str:
    """
    Download and save article HTML depending on domain logic.
    - DG requires headful mode
    - GTY uses networkidle wait in headless
    """
    with sync_playwright() as p:
        headless = not ("desiringgod.org" in domain)
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        print(f"Visiting {url} ({'headless' if headless else 'headful'})")
        page.goto(url, timeout=60000)

        if False and 'gty.org' in domain:
            page.wait_for_load_state('networkidle')

        html = page.content()
        with open(TEMP_HTML, 'w', encoding='utf-8') as f:
            f.write(html)

        browser.close()
    return TEMP_HTML

def normalize_text(text: str) -> str:
    # Normalize hyphens
    text = re.sub(r"[–—−‒―]", "-", text)

    # Remove weird linebreaks and tabs
    text = re.sub(r"[\n\r\t]", " ", text)

    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def extract_paragraphs_from_dg(html_path: str) -> str:
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    body = soup.select_one("div.resource__body")
    if not body:
        return ""

    # Extract <p> contents with inner text of children separated by spaces
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

def process_article(url: str):
    """
    Generalized dispatcher for processing articles from DesiringGod or GTY.
    """
    ensure_dirs()
    data = load_sentences_json()

    if url_already_processed(data, url):
        print(f"URL already processed: {url}")
        return

    domain = urlparse(url).netloc
    html_path = download_and_save_article(url, domain)

    if 'desiringgod.org' in domain:
        article_text = extract_paragraphs_from_dg(html_path)
    elif 'gty.org' in domain:
        article_text = extract_paragraphs_from_gty(html_path)
    else:
        print(f"Unsupported domain: {domain}")
        return

    sentences = sent_tokenize(article_text)
    bible_sentences = [s.strip() for s in sentences if contains_bible_book(s)]

    if bible_sentences:
        data.append({
            "url": url,
            "sentences": sorted(bible_sentences)
        })
        save_sentences_json(data)
        print(f"Added {len(bible_sentences)} sentences from {url}")
    else:
        print(f"No Bible-referencing sentences found in {url}")

# Example usage
if __name__ == "__main__":
    test_urls = [
        "https://www.desiringgod.org/articles/bring-the-bible-home-to-your-heart",
        "https://www.gty.org/library/blog/B200723"
    ]
    for url in test_urls:
        process_article(url)
