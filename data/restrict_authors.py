import json
import os

# === Configuration ===
ALLOWED_AUTHORS = ["John Piper"]
RESOURCES_JSON = "data/resources_dg.json"
URLS_TXT = "data/resource_urls.txt"

def load_resources(filepath):
    """Load the JSON list of resource dicts from Desiring God."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} does not exist.")
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)

def load_all_urls(filepath):
    """Load all URLs from the existing resource_urls.txt."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_allowed_dg_urls(resources, allowed_authors):
    """
    Return desiringgod.org URLs where the author is in allowed_authors.
    """
    return {
        res["url"]
        for res in resources
        if res.get("url", "").startswith("https://www.desiringgod.org")
        and res.get("author") in allowed_authors
    }

def filter_urls(all_urls, allowed_dg_urls):
    """
    Keep:
      - All non-desiringgod.org URLs
      - Only approved desiringgod.org URLs
    """
    filtered = []
    for url in all_urls:
        if "desiringgod.org" in url:
            if url in allowed_dg_urls:
                filtered.append(url)
        else:
            filtered.append(url)
    return filtered

def write_urls(urls, filepath):
    """Write the final filtered URLs to file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for url in sorted(set(urls)):
            f.write(url + "\n")
    print(f"✅ Wrote {len(urls)} URLs to {filepath}")

def main():
    resources = load_resources(RESOURCES_JSON)
    all_urls = load_all_urls(URLS_TXT)
    allowed_dg_urls = get_allowed_dg_urls(resources, ALLOWED_AUTHORS)
    final_urls = filter_urls(all_urls, allowed_dg_urls)
    write_urls(final_urls, URLS_TXT)

if __name__ == "__main__":
    main()
