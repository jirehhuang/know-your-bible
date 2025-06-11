from xml.etree import ElementTree as ET
import json
from collections import defaultdict
import os

def xml_to_json(xml_path: str) -> dict:
    """
    Convert a Bible XML file to a nested dictionary format suitable for JSON serialization.

    Args:
        xml_path (str): Path to the XML file.

    Returns:
        dict: A dictionary structured as {Book: [[verse, verse, ...], [verse, verse, ...], ...]}
              where each list of lists corresponds to chapters and verses.
    """
    print(f"Parsing XML file: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    bible_dict = defaultdict(list)

    # Iterate over each book in the XML
    for book in root.findall("b"):
        book_name = book.attrib["n"]
        print(f"  Found book: {book_name}")

        # Iterate over each chapter in the book
        for chapter_index, chapter in enumerate(book.findall("c"), start=1):
            verses = []
            for verse_index, verse in enumerate(chapter.findall("v"), start=1):
                text = (verse.text or "").strip()
                verses.append(text)
            print(f"    Processed Chapter {chapter_index} with {len(verses)} verses.")
            bible_dict[book_name].append(verses)

    print(f"Finished parsing: {xml_path}")
    return bible_dict

if __name__ == "__main__":
    print("Starting XML to JSON conversion...")

    # Look through all XML files in the current directory
    for filename in os.listdir("translations"):
        if filename.lower().endswith(".xml"):
            base_name = os.path.splitext(filename)[0].lower()
            json_filename = f"{base_name}.json"

            print(f"\n---\nFound XML file: {filename}")
            print(f"Target JSON filename: {json_filename}")

            try:
                # Convert and write JSON file
                data = xml_to_json(os.path.join("translations", filename))
                with open(os.path.join("translations", json_filename), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Successfully wrote: {json_filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    print("\nAll done.")
