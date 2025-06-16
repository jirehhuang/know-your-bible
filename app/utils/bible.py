import json
from pathlib import Path
from datetime import datetime

# Constants
OT_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
    "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
    "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi"
]

NT_BOOKS = [
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]


def get_bible_translation(translation: str = "esv", bool_counts: bool = False) -> dict:
    """
    Load the specified Bible translation, optionally with verse usage counts.

    Args:
        translation (str): The translation to load (e.g., "esv").
        bool_counts (bool): Whether to augment verses with count data.

    Returns:
        dict: Loaded Bible data.
    """
    path = Path(f"translations/{translation.lower()}.json")
    if not path.exists():
        print(f"[WARNING] Bible file not found: {path}")
        return {}

    with open(path, "r") as f:
        bible = json.load(f)
    print(f"[DEBUG] Loaded Bible from {path}")

    if bool_counts:
        counts_path = Path("data/verse_counts.json")
        if counts_path.exists():
            with open(counts_path, "r") as f:
                counts = json.load(f)
            print(f"[DEBUG] Loaded verse counts from {counts_path}")

            for book, chapters in counts.items():
                for chapter, verses in chapters.items():
                    for verse, count_data in verses.items():
                        try:
                            bible[book][chapter][verse].update(count_data)
                        except KeyError:
                            print(f"[WARNING] Skipping missing verse: {book} {chapter}:{verse}")
        else:
            print(f"[WARNING] verse_counts.json not found at {counts_path}")

    return bible

def add_user_data(user_data: list, bible: dict):
    """
    Adds user-specific data to the appropriate verse in the Bible structure.

    Args:
        user_data (list): List of dicts with keys including 'user_id', 'reference', 'timestamp'.
        bible (dict): Bible structure to update in place.

    Example input record:
        {
            "user_id": "abc123",
            "reference": "1 Corinthians 10:13",
            "timestamp": "2024-10-01T12:34:56",
            ...
        }
    """
    latest_data = {}

    ## Organize most recent entry for each (user_id, reference)
    for item in user_data:
        user_id = item.get("user_id")
        reference = item.get("reference")
        timestamp = item.get("timestamp")
        if not (user_id and reference and timestamp):
            continue

        key = (user_id, reference)
        dt = datetime.fromisoformat(timestamp)

        if key not in latest_data or dt > latest_data[key]["_dt"]:
            item["_dt"] = dt  # Temporary for sorting
            latest_data[key] = item

    ## Insert into Bible structure
    for (user_id, reference), item in latest_data.items():
        try:
            book_verse, verse_part = reference.rsplit(" ", 1)
            if ":" not in verse_part:
                print(f"[WARNING] Skipping malformed reference: {reference}")
                continue
            chapter, verse = verse_part.split(":")
            book = book_verse.strip()
            chapter = chapter.lstrip("0")
            verse = verse.lstrip("0")

            if book in bible and chapter in bible[book] and verse in bible[book][chapter]:
                if user_id not in bible[book][chapter][verse]:
                    bible[book][chapter][verse][user_id] = item
                else:
                    ## Optional: merge/update if desired
                    bible[book][chapter][verse][user_id] = item
            else:
                print(f"[WARNING] Verse not found in Bible: {reference}")
        except Exception as e:
            print(f"[ERROR] Failed to insert user data for reference {reference}: {e}")

    ## Clean up temp
    for record in latest_data.values():
        record.pop("_dt", None)


## Global load (without counts by default)
BIBLE = get_bible_translation(bool_counts=False)

CHAPTER_COUNTS = {book: len(chapters) for book, chapters in BIBLE.items()}
BOOK_TO_TESTAMENT = {book: "OT" for book in OT_BOOKS} | {book: "NT" for book in NT_BOOKS}

## Build list of all authors from verse_counts.json
AUTHORS = set()
verse_counts_path = Path("data/verse_counts.json")
if verse_counts_path.exists():
    with open(verse_counts_path, "r") as f:
        data = json.load(f)
        for book_data in data.values():
            for chapter_data in book_data.values():
                for verse_data in chapter_data.values():
                    AUTHORS.update(k for k in verse_data if k != "count")
else:
    print("[WARNING] verse_counts.json not found for AUTHORS extraction")

AUTHORS = sorted(AUTHORS)


def get_top_n(n=10, authors=["all"], counts_file="data/verse_counts.json"):
    """
    Get the top N verses with the highest mention counts.

    Args:
        n (int): Number of top verses to return.
        authors (list): List of authors to include or ["all"] for total count.

    Returns:
        list of tuples: (book, chapter, verse, count)
    """
    results = []

    path = Path(counts_file)
    if not path.exists():
        print(f"[ERROR] verse_counts.json not found at {path}")
        return []

    with open(path, "r") as f:
        counts_data = json.load(f)

    for book, chapters in counts_data.items():
        for chapter, verses in chapters.items():
            for verse, count_data in verses.items():
                if "all" in authors:
                    count = count_data.get("count", 0)
                else:
                    count = sum(count_data.get(author, 0) for author in authors if author in count_data)
                results.append((book, chapter, verse, count))

    results.sort(key=lambda x: x[3], reverse=True)
    return results[:n]
