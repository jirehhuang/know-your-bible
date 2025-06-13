import json
from pathlib import Path

def get_bible_translation(translation: str="esv", bool_biblerefs: bool=True) -> dict:
    """
    Load the specified Bible translation from the translations directory.
    
    Args:
        translation (str): The translation to load, default is "esv".
        
    Returns:
        dict: The loaded Bible translation.
    """
    bible = {}

    if bool_biblerefs:
        try:
            translation_path = Path(f"translations/{translation.lower()}_biblerefs.json")
            with open(translation_path, "r") as f:
                bible = json.load(f)
            print(f"[DEBUG] Loaded Bible with biblerefs from {translation_path}")
        except FileNotFoundError as e:
            print(f"[WARNING] Bible with biblerefs not found: {e}")

    if not bible:
        translation_path = Path(f"translations/{translation.lower()}.json")
        with open(translation_path, "r") as f:
            bible = json.load(f)
        print(f"[DEBUG] Loaded Bible from {translation_path}")

    return bible

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

BIBLE = get_bible_translation(bool_biblerefs=False)

CHAPTER_COUNTS = {book: len(chapters) for book, chapters in BIBLE.items()}

BOOK_TO_TESTAMENT = {book: "OT" for book in OT_BOOKS} | {book: "NT" for book in NT_BOOKS}
