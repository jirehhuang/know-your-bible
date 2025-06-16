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
    r'(?P<ref_block>' + \
        r'(?:\d+:[\d,\- ]+(?:\s*[;,]\s*\d*:?[\d,\- ]+)*)+' + \
    r')(?=\s+(?:' + '|'.join(re.escape(book) for book in BIBLE_BOOKS) + r')\b|\s*$|[^\w:])'

def fix_malformed(sentence: str) -> str:
    replacements = {
        "Jeremiah 32:374 1": "Jeremiah 32:37-41",
        "Ephesians 5:252 7": "Ephesians 5:25-27",
        "Matthew 27:27 37": "Matthew 27:27-37",
        "Colossians 1:212 2": "Colossians 1:21-22",
        "Acts 20:24 21 ; 19": "Acts 20:24; 21:19",
        "Matthew 18:8 25:42": "Matthew 18:8; 25:42",
        "Hebrews 13:13 10:32": "Hebrews 13:13; 10:32",
        "1 Peter 1:6 7": "1 Peter 1:6-7",
    }
    for old, new in replacements.items():
        sentence = sentence.replace(old, new)

    return sentence

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
    matches = list(re.finditer(r'\b(' + '|'.join(re.escape(book) for book in BIBLE_BOOKS) + r')\b', sentence))
    reference_objs = []

    for i, match in enumerate(matches):
        book = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sentence)
        chunk = sentence[start:end].strip()

        ## Extract the reference block using the original pattern, but limited to this chunk
        book_match = re.match(
            r'^' + re.escape(book) + r'\s+(?P<ref_block>(?:\d+:[\d,\- ]+(?:\s*[;,]\s*\d*:?[\d,\- ]+)*)+)',
            chunk
        )
        if not book_match:
            continue

        ref_block = book_match.group("ref_block").strip()

        chapter_groups = [v.strip() for v in ref_block.split(";") if v.strip()]
        verses = []
        chapters = set()
        current_chapter = None

        for group in chapter_groups:
            original_group = group  # Save for warning messages

            if ":" in group:
                parts = group.split(":")
                if len(parts) == 2:
                    chapter, verse_part = parts
                    current_chapter = chapter.strip()
                    verse_part = verse_part.strip()
                else:
                    print(f"[WARN] Skipping malformed group (too many colons): {book} {group}")
                    continue
            elif current_chapter:
                verse_part = group.strip()
            else:
                print(f"[WARN] Skipping malformed group (no chapter context): {book} {group}")
                continue

            ## Try expanding verses; skip only bad entries
            expanded = []
            for vp in re.split(r'[;,]', verse_part):
                vp = vp.strip()
                if not vp:
                    continue
                try:
                    if '-' in vp:
                        try:
                            start, end = map(int, vp.split('-'))
                            expanded.extend([f"{book} {current_chapter}:{v}" for v in range(start, end + 1)])
                        except ValueError:
                            ## Try to extract the valid number before dash
                            try:
                                start = int(vp.split('-')[0])
                                expanded.append(f"{book} {current_chapter}:{start}")
                                print(f"[WARN] Incomplete range in '{book} {original_group}': salvaged {start}")
                            except ValueError:
                                print(f"[WARN] Malformed range in '{book} {original_group}': {vp}")
                            continue
                    else:
                        v = int(vp)
                        expanded.append(f"{book} {current_chapter}:{v}")
                except ValueError:
                    print(f"[WARN] Skipping malformed verse segment in '{book} {original_group}': {vp}")
                    continue

            if not expanded:
                print(f"[WARN] All parts malformed in '{book} {original_group}', skipping.")
                continue

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
    print(f"[INFO] Compiling nested verse_counts.json by book > chapter > verse...")

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
                try:
                    ## Expect format: "Book Chapter:Verse"
                    book_part, verse_part = verse.rsplit(" ", 1)
                    chapter, verse_num = verse_part.split(":")
                    book = book_part.strip()
                    chapter = chapter.strip()
                    verse_num = verse_num.strip()
                except ValueError:
                    print(f"[WARN] Skipping malformed verse: {verse}")
                    continue

                ## Initialize nested structure
                if book not in verse_counts:
                    verse_counts[book] = {}
                if chapter not in verse_counts[book]:
                    verse_counts[book][chapter] = {}
                if verse_num not in verse_counts[book][chapter]:
                    verse_counts[book][chapter][verse_num] = {}

                ## Count per author
                verse_entry = verse_counts[book][chapter][verse_num]
                verse_entry[author] = verse_entry.get(author, 0) + 1

    ## Add total count per verse
    for book_data in verse_counts.values():
        for chapter_data in book_data.values():
            for verse_data in chapter_data.values():
                total = sum(count for k, count in verse_data.items() if k != "count")
                verse_data["count"] = total

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(verse_counts, f, indent=2)

    print(f"[INFO] Wrote nested verse usage counts to {output_path}")
    print(f"[INFO] Total books: {len(verse_counts)}")


def main():
    input_path = Path("data/resources.json")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    skipped = 0
    trivial = 0
    errored = 0

    for url, entry in data.items():
        ## Clear any existing 'references' key
        if "references" in entry:
            del entry["references"]

        try:
            if isinstance(entry.get("references"), list):
                skipped += 1
                continue

            sentences = entry.get("sentences")
            scripture = entry.get("scripture")

            if sentences is None and not scripture:
                print(f"[WARN] [{url}] No 'sentences' or 'scripture' field found.")
                entry["references"] = []
                trivial += 1
                continue


            ## Handle sentence + scripture presence
            all_refs = []
            sentence_inputs = []

            if isinstance(sentences, list):
                sentence_inputs.extend(sentences)
            if isinstance(scripture, str) and scripture.strip():
                sentence_inputs.append(scripture.strip())

            for sentence in sentence_inputs:
                if not isinstance(sentence, str):
                    continue
                
                ## Manually clean up sentences
                sentence = fix_malformed(sentence)

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
    print(f"[INFO] Trivial (no scripture or sentences): {trivial}")
    print(f"[INFO] Errored: {errored}")

    verse_counts_path = Path("data/verse_counts.json")
    compile_verse_counts(input_path, verse_counts_path)


if __name__ == "__main__":
    main()
