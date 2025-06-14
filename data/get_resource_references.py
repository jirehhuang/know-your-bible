import sys
import json
import re
from pathlib import Path
from collections import defaultdict

## Adjust path to import BIBLE
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.utils.bible import BIBLE

BIBLE_BOOKS = set(BIBLE.keys())

## Match book name + chapter:verse pattern (loose spacing allowed)
BOOK_PATTERN = r'(?:(?<=\s)|^)' + \
    r'(?P<book>' + '|'.join(re.escape(book) for book in BIBLE_BOOKS) + r')\s*' + \
    r'(?P<ref_block>(?:\d+:[\d,\- ]+(?:\s*[;,]\s*\d*:?[\d,\- ]+)*)+)'

def expand_verses(chapter: str, verses: str, book: str):
    refs = []
    parts = [p.strip() for p in re.split(r'[;,]', verses) if p.strip()]
    for part in parts:
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                refs.extend([f"{book} {chapter}:{v}" for v in range(start, end + 1)])
            except ValueError:
                continue
        else:
            refs.append(f"{book} {chapter}:{part}")
    return refs

def extract_reference_objects(sentence: str):
    reference_objs = []

    for match in re.finditer(BOOK_PATTERN, sentence):
        book = match.group("book")
        ref_block = match.group("ref_block").strip()

        chapter_groups = [v.strip() for v in ref_block.split(";") if v.strip()]
        verses = []
        chapters = set()
        current_chapter = None

        for group in chapter_groups:
            if ":" in group:
                parts = group.split(":")
                if len(parts) == 2:
                    chapter, verse_part = parts
                    current_chapter = chapter.strip()
                    verse_part = verse_part.strip()
                else:
                    continue
            elif current_chapter:
                verse_part = group.strip()
            else:
                continue

            expanded = expand_verses(current_chapter, verse_part, book)
            chapters.add(f"{book} {current_chapter}")
            verses.extend(expanded)

        reference_objs.append({
            "reference": f"{book} {ref_block}",
            "book": book,
            "chapters": sorted(chapters),
            "verses": verses,
        })

    return reference_objs

def compile_verse_counts(input_path: Path, output_path: Path):
    print(f"[INFO] Compiling verse_counts.json...")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    verse_counts = {}

    for url, entry in data.items():
        author = entry.get("author", "Unknown")
        references = entry.get("references")

        if not isinstance(references, list):
            continue

        for ref_obj in references:
            for verse in ref_obj.get("verses", []):
                if verse not in verse_counts:
                    verse_counts[verse] = {}
                verse_counts[verse][author] = verse_counts[verse].get(author, 0) + 1

    # Add total count for each verse
    for verse, counts in verse_counts.items():
        total = sum(count for auth, count in counts.items() if auth != "count")
        counts["count"] = total

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(verse_counts, f, indent=2)

    print(f"[INFO] Wrote verse usage counts to {output_path}")
    print(f"[INFO] Total unique verses: {len(verse_counts)}")

    sample = dict(list(verse_counts.items())[:3])
    print(f"[DEBUG] Sample verse counts:\n{json.dumps(sample, indent=2)}")


def main():
    input_path = Path("data/resources.json")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    skipped = 0
    errored = 0

    for url, entry in data.items():
        try:
            if isinstance(entry.get("references"), list):
                skipped += 1
                continue

            if entry.get("sentences") is None:
                entry["references"] = None
                errored += 1
                continue

            if len(entry["sentences"]) == 0:
                entry["references"] = []
                continue

            all_refs = []
            for sentence in entry["sentences"]:
                refs = extract_reference_objects(sentence)
                all_refs.extend(refs)

            entry["references"] = all_refs
            updated += 1

        except Exception as e:
            print(f"[ERROR] Failed processing {url}: {e}")
            entry["references"] = None
            errored += 1

    with input_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[INFO] Finished processing resources.json")
    print(f"[INFO] Updated: {updated}")
    print(f"[INFO] Skipped (already populated): {skipped}")
    print(f"[INFO] Errored or invalid: {errored}")

    verse_counts_path = Path("data/verse_counts.json")
    compile_verse_counts(input_path, verse_counts_path)

if __name__ == "__main__":
    main()
