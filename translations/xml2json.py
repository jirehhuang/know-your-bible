from xml.etree import ElementTree as ET
import json
import os

def xml_to_json(xml_path: str) -> dict:
    """
    Convert a Bible XML file to a nested dictionary format suitable for JSON serialization.

    Structure:
    {
      "BookName": {
        chapter_number: {
          verse_number: {
            "text": "Verse text..."
          },
          ...
        },
        ...
      },
      ...
    }

    Args:
        xml_path (str): Path to the XML file.

    Returns:
        dict: Nested dictionary of books, chapters, and verses with text.
    """
    print(f"Parsing XML file: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    bible_dict = {}

    for book in root.findall("b"):
        book_name = book.attrib["n"]
        print(f"  Found book: {book_name}")
        book_dict = {}

        for chapter_index, chapter in enumerate(book.findall("c"), start=1):
            chapter_dict = {}

            for verse in chapter.findall("v"):
                verse_num = int(verse.attrib["n"])
                text = (verse.text or "").strip()
                chapter_dict[verse_num] = {
                    "text": text,
                }

            print(f"    Processed Chapter {chapter_index} with {len(chapter_dict)} verses.")
            book_dict[chapter_index] = chapter_dict

        bible_dict[book_name] = book_dict

    print(f"Finished parsing: {xml_path}")
    return bible_dict

if __name__ == "__main__":
    print("Starting XML to JSON conversion...")

    # Look through all XML files in the "translations" directory
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
