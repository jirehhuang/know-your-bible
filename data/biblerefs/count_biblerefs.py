import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.utils.bible import BIBLE

def is_valid_ref(book, chapter, verse):
    return (
        book in BIBLE and
        chapter in BIBLE[book] and
        verse in BIBLE[book][chapter]
    )

def parse_reference(ref):
    """Parse 'Romans 8:31' into ('Romans', '8', '31')"""
    match = re.match(r"^(.*?)\s+(\d+):(\d+)$", ref)
    if not match:
        return None, None, None
    book, chapter, verse = match.groups()
    return book.strip(), chapter.strip(), verse.strip()

def count_biblerefs(input_file="data/biblerefs/biblerefs.txt", output_file="data/biblerefs/biblerefs.json"):
    input_path = Path(input_file)
    output_path = Path(output_file)

    if not input_path.exists():
        print(f"[Error] File not found: {input_file}")
        return

    ## Read and clean references
    with open(input_path, "r", encoding="utf-8") as f:
        refs = [line.strip() for line in f if line.strip()]

    ## Filter only valid references
    valid_refs = []
    for ref in refs:
        book, chapter, verse = parse_reference(ref)
        if book and chapter and verse and is_valid_ref(book, chapter, verse):
            valid_refs.append(f"{book} {chapter}:{verse}")
        else:
            print(f"[Skipping] Invalid reference: {ref}")

    ## Count occurrences
    counts = Counter(valid_refs)

    ## Sort by count descending
    sorted_refs = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    ## Convert to desired JSON format
    result = [{"reference": ref, "count": count} for ref, count in sorted_refs]

    ## Write to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"✅ Saved {len(result)} valid counted references to {output_file}")

## Execute
count_biblerefs()
