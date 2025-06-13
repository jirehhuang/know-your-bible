import sys
import json
import re
from pathlib import Path

## Adjust path to import BIBLE
sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.utils.bible import BIBLE
BIBLE_BOOKS = set(BIBLE.keys())

## Match book name + chapter:verse pattern (loose spacing allowed)
BOOK_PATTERN = r'(?:(?<=\s)|^)' + \
    r'(?P<book>' + '|'.join(re.escape(book) for book in BIBLE_BOOKS) + r')\s*' + \
    r'(?P<ref_block>(?:\d+:[\d,\- ]+(?:\s*[;,]\s*\d*:?[\d,\- ]+)*)+)'

def expand_verses(chapter: str, verses: str, book: str):
    """
    Expands verse fragments like '6 , 12 , 21-22' into full refs like ['Book 1:6', ..., 'Book 1:22']
    """
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

        ## Split by semicolons for chapter separation
        chapter_groups = [v.strip() for v in ref_block.split(";") if v.strip()]
        references = []
        current_chapter = None

        for group in chapter_groups:
            if ":" in group:
                ## New chapter explicitly stated
                parts = group.split(":")
                if len(parts) == 2:
                    chapter, verse_part = parts
                    current_chapter = chapter.strip()
                    verse_part = verse_part.strip()
                else:
                    continue  # malformed
            elif current_chapter:
                ## No new chapter specified, use previous
                verse_part = group.strip()
            else:
                continue  # skip if no context

            expanded = expand_verses(current_chapter, verse_part, book)
            references.extend(expanded)

        reference_objs.append({
            "reference": f"{book} {ref_block}",
            "references": references,
            # "book": book,
            # "chapter": int(current_chapter) if current_chapter else None,
        })

    return reference_objs

def main():
    input_path = Path("data/biblementions/sentences.json")
    txt_output_path = Path("data/biblementions/references.txt")
    json_output_path = Path("data/biblementions/references.json")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    all_expanded_refs = []
    all_reference_objs = []

    print(f"[INFO] Loaded {len(data)} entries from sentences.json")

    total_sentences = 0
    total_ref_objects = 0

    for entry in data:
        for sentence in entry["sentences"]:
            total_sentences += 1
            refs = extract_reference_objects(sentence)
            for ref_obj in refs:
                total_ref_objects += 1
                all_reference_objs.append(ref_obj)
                all_expanded_refs.extend(ref_obj["references"])

    print(f"[INFO] Processed {total_sentences} sentences")
    print(f"[INFO] Found {total_ref_objects} Scripture reference blocks")
    print(f"[INFO] Extracted {len(all_expanded_refs)} total individual verse references (duplicates included)")

    if all_reference_objs:
        print(f"\n[DEBUG] First 3 reference objects:")
        for r in all_reference_objs[:3]:
            print(json.dumps(r, indent=2))

    ## Write text file: one reference per line
    with txt_output_path.open("w", encoding="utf-8") as f:
        for ref in all_expanded_refs:
            f.write(ref + "\n")

    ## Write JSON file with structure: reference + expanded list
    with json_output_path.open("w", encoding="utf-8") as f:
        json.dump(all_reference_objs, f, indent=2)

    print(f"\n[INFO] Wrote expanded references to {txt_output_path}")
    print(f"[INFO] Wrote reference objects to {json_output_path}")

if __name__ == "__main__":
    main()
