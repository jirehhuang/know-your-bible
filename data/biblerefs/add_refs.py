import json
import re
from pathlib import Path

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def parse_reference(ref):
    # Match examples like: "Romans 8:31", "1 John 3:16"
    match = re.match(r"(?:(\d)\s*)?([A-Za-z ]+)\s+(\d+):(\d+)", ref)
    if not match:
        raise ValueError(f"Invalid reference format: {ref}")
    
    prefix, book, chapter, verse = match.groups()
    book = f"{prefix} {book}" if prefix else book
    return book.strip(), chapter.strip(), verse.strip()

def increment_reference_counts(bible, biblerefs):
    for ref in biblerefs:
        try:
            book, chapter, verse = parse_reference(ref)

            if book not in bible:
                print(f"[Warning] Book not found in Bible data: {book}")
                continue
            if chapter not in bible[book]:
                print(f"[Warning] Chapter {chapter} not found in {book}")
                continue
            if verse not in bible[book][chapter]:
                print(f"[Warning] Verse {verse} not found in {book} {chapter}")
                continue

            verse_data = bible[book][chapter][verse]
            verse_data["biblerefs"] = verse_data.get("biblerefs", 0) + 1

        except Exception as e:
            print(f"[Error] Failed to process {ref}: {e}")

    return bible

# Load data
BIBLE_PATH = Path("translations/esv.json")
REFS_PATH = Path("data/biblerefs/biblerefs.txt")
OUTPUT_PATH = Path("translations/esv_biblerefs.json")

bible = load_json(BIBLE_PATH)
with open(REFS_PATH, "r", encoding="utf-8") as f:
    biblerefs = [line.strip() for line in f if line.strip()]

# Process
updated_bible = increment_reference_counts(bible, biblerefs)

# Save
save_json(updated_bible, OUTPUT_PATH)
print(f"\n✅ Done. Updated Bible with biblerefs saved to {OUTPUT_PATH}")
