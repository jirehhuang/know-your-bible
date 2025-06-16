import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from example_cases import example_cases

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.utils.bible import BIBLE

BIBLE_BOOKS = set(BIBLE.keys())

## Default replacement corrections
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

def apply_replacements(sentence: str) -> str:
    for wrong, correct in replacements.items():
        sentence = sentence.replace(wrong, correct)
    ## Normalize all hyphens
    sentence = sentence.replace("–", "-").replace("—", "-").replace(" - ", "-")
    return sentence

def get_book_and_rest(match: str) -> Tuple[str, str]:
    """Splits 'Book Chapter:Verse' string into ('Book', 'Chapter:Verse')"""
    tokens = match.strip().split()
    for i in range(len(tokens), 0, -1):
        book_candidate = ' '.join(tokens[:i])
        if book_candidate in BIBLE_BOOKS:
            return book_candidate, ' '.join(tokens[i:])
    return '', match  # Shouldn't happen if regex is good

def parse_verse_range(book: str, ref: str) -> List[str]:
    result = []
    parts = [s.strip() for s in re.split(r'[;,]', ref)]
    last_chapter = None

    for part in parts:
        if not part:
            continue

        if '-' in part:
            start_str, end_str = map(str.strip, part.split('-', 1))

            start_chap, start_verse, start_suffix = parse_chapter_verse(start_str, last_chapter, book)
            end_chap, end_verse, end_suffix = parse_chapter_verse(end_str, start_chap, book)

            try:
                start_chap_i = int(start_chap)
                start_verse_i = int(start_verse)
                end_chap_i = int(end_chap)
                end_verse_i = int(end_verse)
            except ValueError:
                try:
                    start_verse_i = int(re.match(r'(\d+)', start_verse).group(1))
                    end_verse_i = int(re.match(r'(\d+)', end_verse).group(1))
                    start_chap_i = int(start_chap)
                    end_chap_i = int(end_chap)
                except Exception:
                    print(f"Warning: could not parse range numbers in {start_str}-{end_str}")
                    continue

            ## Skip if backward range
            if (start_chap_i > end_chap_i) or (start_chap_i == end_chap_i and start_verse_i > end_verse_i):
                print(f"Warning: backward range {start_str}-{end_str} in {book} {ref}. Using only {start_str}.")
                if str(start_chap) in BIBLE[book] and str(start_verse) in BIBLE[book][str(start_chap)]:
                    result.append(f"{book} {start_chap}:{start_verse}")
                continue

            for chap in range(start_chap_i, end_chap_i + 1):
                verse_start = start_verse_i if chap == start_chap_i else 1
                try:
                    verse_end = (
                        end_verse_i if chap == end_chap_i else max(map(int, BIBLE[book][str(chap)].keys()))
                    )
                except KeyError:
                    print(f"Warning: {book} {chap} not found in BIBLE")
                    continue

                for v in range(verse_start, verse_end + 1):
                    if str(chap) in BIBLE[book] and str(v) in BIBLE[book][str(chap)]:
                        result.append(f"{book} {chap}:{v}")
                    else:
                        print(f"Warning: {book} {chap}:{v} not found")

        else:
            chap, verse, suffix = parse_chapter_verse(part, last_chapter, book)
            try:
                if str(chap) in BIBLE[book] and str(verse) in BIBLE[book][str(chap)]:
                    result.append(f"{book} {chap}:{verse}{suffix}")
                else:
                    print(f"Warning: {book} {chap}:{verse}{suffix} not found")
            except Exception as e:
                print(f"Error accessing BIBLE for {book} {chap}:{verse}{suffix}: {e}")
        last_chapter = chap

    return result

def parse_chapter_verse(ref: str, fallback_chapter=None, book=None) -> Tuple[str, str]:
    """
    Parses 'chapter:verse' or just 'verse' with fallback chapter.
    Separates verse number from trailing letters like '26a' -> ('26', 'a').
    Returns (chapter, verse_number), suffix separately if needed.
    """
    if ':' in ref:
        chapter, verse = ref.split(':', 1)
    else:
        ## Single-chapter book fallback
        if book and len(BIBLE[book]) == 1:
            chapter = '1'
            verse = ref
        else:
            chapter = str(fallback_chapter)
            verse = ref

    ## Extract trailing letter suffix from verse, e.g. '26a' -> '26', 'a'
    m = re.match(r'(\d+)([a-zA-Z]*)$', verse)
    if m:
        verse_num = m.group(1)
        suffix = m.group(2)
    else:
        verse_num = verse
        suffix = ''

    return chapter, verse_num, suffix

def extract_references(sentence: str) -> List[Dict[str, Any]]:
    sentence = apply_replacements(sentence)
    book_pattern = '|'.join(sorted(BIBLE_BOOKS, key=lambda x: -len(x)))
    regex = re.compile(
        rf'\b({book_pattern})\s+'
        r'((?:\d+(?::\d+)?(?:[-–]\d+(?::\d+)?)?[a-zA-Z]?'
        r'(?:\s*[;,]\s*\d+(?::\d+)?(?:[-–]\d+(?::\d+)?)?[a-zA-Z]?)*))',
        re.IGNORECASE
    )

    references = []
    for match in regex.finditer(sentence):
        book, ref_str = match.groups()
        book = book.strip()

        # Fix edge case: remove letters accidentally attached to numbers
        clean_ref_str = re.sub(r'([0-9]+)[a-zA-Z]', r'\1', ref_str)

        full_reference = f"{book} {clean_ref_str}".strip()
        verse_list = parse_verse_range(book, clean_ref_str)
        if not verse_list:
            continue

        chapters = sorted(set(v.rsplit(':', 1)[0] for v in verse_list))
        references.append({
            "reference": full_reference,
            "book": book,
            "chapters": chapters,
            "verses": verse_list
        })

    return references

## Test harness
def test_cases(cases):
    for i, case in enumerate(cases):
        i = i+1
        print(f"Test case {i}: {case['sentence']}")
        expected = case["references"]
        actual = extract_references(case["sentence"])

        # Check number of references
        if len(expected) != len(actual):
            print("Expected:", expected)
            print("Actual:", actual)
            raise AssertionError(f"Test case {i} failed!")

        for exp_ref, act_ref in zip(expected, actual):
            for key in ['reference', 'book']:
                if exp_ref[key] != act_ref[key]:
                    print("Expected:", exp_ref)
                    print("Actual:", act_ref)
                    raise AssertionError(f"Test case {i} failed!")

            # Compare chapters and verses as sets
            if set(exp_ref["chapters"]) != set(act_ref["chapters"]) or \
               set(exp_ref["verses"]) != set(act_ref["verses"]):
                print("Expected:", exp_ref)
                print("Actual:", act_ref)
                raise AssertionError(f"Test case {i} failed!")

        print(f"✅ Test case {i} passed\n")

## Execute
test_cases(example_cases)
