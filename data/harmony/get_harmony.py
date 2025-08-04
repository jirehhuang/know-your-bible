import os
import requests
from bs4 import BeautifulSoup
import json

BASE_DIR = "data/harmony"
HTML_PATH = os.path.join(BASE_DIR, "harmony.html")
JSON_PATH = os.path.join(BASE_DIR, "harmony.json")
URL = "https://www.blueletterbible.org/study/harmony/index.cfm"

def fetch_and_save_html():
    os.makedirs(BASE_DIR, exist_ok=True)
    print(f"[INFO] Downloading {URL}")
    response = requests.get(URL)
    response.raise_for_status()
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"[INFO] Saved HTML to {HTML_PATH}")

def parse_harmony_div_structure(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("div", class_="harmony-table")
    rows = table.find_all("div", class_="harmony-table-row")

    data = []
    current_category = None

    for row in rows:
        cat_div = row.find("div", class_="header-columns")
        if cat_div:
            current_category = cat_div.get_text(strip=True)
            continue

        cols = row.find_all("div", class_=lambda c: c and c.startswith("medium-"))
        if len(cols) >= 5:
            subject = cols[0].get_text(strip=True)
            gospels = ["Matthew", "Mark", "Luke", "John"]
            references = []

            for gospel, col in zip(gospels, cols[1:]):
                ref = col.get_text(strip=True)
                if ref:
                    # If it's not already prefixed with the book name
                    if ":" in ref and not ref.lower().startswith(gospel.lower()):
                        ref = f"{gospel} {ref}"
                    references.append(ref)

            if references:
                data.append({
                    "category": current_category,
                    "subject": subject,
                    "references": references
                })

    return data

def main():
    fetch_and_save_html()
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    harmony_data = parse_harmony_div_structure(html)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(harmony_data, f, indent=2)

    print(f"[INFO] Extracted {len(harmony_data)} harmony entries to {JSON_PATH}")

if __name__ == "__main__":
    main()
