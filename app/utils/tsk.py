import os
from collections import defaultdict

TSK_PATH = os.path.join("data", "tskxref.txt")

# Map from book abbreviation to full name
TSK_BOOKS = {
    "ge": "Genesis", "ex": "Exodus", "le": "Leviticus", "nu": "Numbers", "de": "Deuteronomy",
    "jos": "Joshua", "jud": "Judges", "ru": "Ruth", "1sa": "1 Samuel", "2sa": "2 Samuel",
    "1ki": "1 Kings", "2ki": "2 Kings", "1ch": "1 Chronicles", "2ch": "2 Chronicles",
    "ezr": "Ezra", "ne": "Nehemiah", "es": "Esther", "job": "Job", "ps": "Psalms",
    "pr": "Proverbs", "ec": "Ecclesiastes", "so": "Song of Solomon", "isa": "Isaiah",
    "jer": "Jeremiah", "la": "Lamentations", "eze": "Ezekiel", "da": "Daniel",
    "ho": "Hosea", "joe": "Joel", "am": "Amos", "ob": "Obadiah", "jon": "Jonah",
    "mic": "Micah", "na": "Nahum", "hab": "Habakkuk", "zep": "Zephaniah", "hag": "Haggi",
    "zec": "Zechariah", "mal": "Malachi", "mt": "Matthew", "mr": "Mark", "lu": "Luke",
    "joh": "John", "ac": "Acts", "ro": "Romans", "1co": "1 Corinthians", "2co": "2 Corinthians",
    "ga": "Galatians", "eph": "Ephesians", "php": "Philippians", "col": "Colossians",
    "1th": "1 Thessalonians", "2th": "2 Thessalonians", "1ti": "1 Timothy", "2ti": "2 Timothy",
    "tit": "Titus", "phm": "Philemon", "heb": "Hebrews", "jas": "James", "1pe": "1 Peter",
    "2pe": "2 Peter", "1jo": "1 John", "2jo": "2 John", "3jo": "3 John", "jude": "Jude",
    "re": "Revelation"
}

# book_key -> full name (for lookup by key)
BOOK_KEY_TO_NAME = {i + 1: name for i, name in enumerate(TSK_BOOKS.values())}

# (book_key, chapter, verse) -> list of (word, reference_list)
TSK_LOOKUP = defaultdict(list)


def load_tsk_data():
    print("[DEUBG] Loading TSK data from file")
    with open(TSK_PATH, "r", encoding="latin-1") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 6:
                continue  # Skip malformed lines
            book_key, chapter, verse, _, word, references = parts
            key = (int(book_key), int(chapter), int(verse))
            TSK_LOOKUP[key].append((word.strip(), references.strip()))

# Load once at module import
load_tsk_data()


def parse_standard_ref(ref: str):
    tokens = ref.strip().split()
    chapter_verse = tokens[-1]
    book = " ".join(tokens[:-1])
    chapter, verse = map(int, chapter_verse.split(":"))

    return book, chapter, verse

def get_tsk_for_ref(ref: str):
    """Takes 'John 3:16' or '1 Corinthians 13:4' and returns TSK entries for that verse."""
    try:
        book, chapter, verse = parse_standard_ref(ref)
    except (ValueError, IndexError):
        return []

    # Convert book to book_key
    book_key = None
    for key, name in BOOK_KEY_TO_NAME.items():
        if name.lower() == book.lower():
            book_key = key
            break
    if book_key is None:
        return []

    results = []
    entries = TSK_LOOKUP.get((book_key, chapter, verse), [])
    for word, ref_str in entries:
        ref_list = []
        for ref in ref_str.split(";"):
            if not ref.strip():
                continue
            abbrev = ref.split()[0] if " " in ref else ref.split(":")[0]
            full_name = TSK_BOOKS.get(abbrev, abbrev)
            formatted = f"{full_name} {ref[len(abbrev):].lstrip()}"
            ref_list.append(formatted)
        results.append({
            "word": word,
            "references": ref_list
        })

    return results


if __name__ == "__main__":
    test_refs = [
        "John 3:16",              # Common NT verse
        "1 Corinthians 13:4",     # Numbered book, NT
        "2 Timothy 3:16",         # Another numbered book
        "Song of Solomon 2:1",    # Multi-word OT book
        "1 Peter 1:3",            # NT, numbered book
        "Ecclesiastes 3:1",       # OT book with longer name
        "Psalms 23:1",            # Psalms (note plural form)
        "Genesis 1:1",            # Beginning of OT
        "Revelation 21:4",        # End of NT
        "Habakkuk 2:4"            # Obscure OT prophet
    ]

    for ref in test_refs:
        print(f"\nTesting: {ref}")
        results = get_tsk_for_ref(ref)
        if not results:
            print("  ❌ No entries found")
        else:
            for entry in results:
                print(f"  Word: {entry['word']}")
                for r in entry['references']:
                    print(f"    → {r}")
