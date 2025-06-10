import os
import json
import random
import boto3
from boto3.dynamodb.conditions import Key
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mangum import Mangum
from pathlib import Path
from datetime import datetime, timezone
from uuid6 import uuid6
from decimal import Decimal
from app.utils.bible import OT_BOOKS, NT_BOOKS, CHAPTER_COUNTS

dynamodb = boto3.resource("dynamodb")
results_table = dynamodb.Table("bible-review-results")
settings_table = dynamodb.Table("bible-review-settings")

app = FastAPI()
static_dir = "app/static"
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory="app/templates")

## Load verse data on startup
with open("translations/esv.json") as f:
    BIBLE = json.load(f)

def get_random_reference(session_id):
    # Example code pulling book and chapter from saved settings
    saved = settings_table.get_item(Key={"user_id": session_id}).get("Item", {})
    selected_books = saved.get("books", list(BIBLE.keys()))
    selected_chapters = saved.get("chapters", {})  # { "Genesis": [1, 2, 3], ... }

    # Pick random book
    book = random.choice(selected_books)

    # If specific chapters selected, pick from them
    if book in selected_chapters and selected_chapters[book]:
        # Convert chapters to int explicitly
        chapter = int(random.choice(selected_chapters[book]))
    else:
        chapter = random.randint(0, len(BIBLE[book]) - 1)

    # Ensure chapter is an int (in case it's a Decimal)
    chapter = int(chapter)

    # Now pick verse
    verse = random.randint(0, len(BIBLE[book][chapter]) - 1)

    return book, chapter, verse

## Helper to get surrounding verses
def get_surrounding_verses(book, chapter, verse):
    verses = BIBLE[book][chapter]
    prev_verse = verses[verse - 1] if verse > 0 else ""
    curr_verse = verses[verse]
    next_verse = verses[verse + 1] if verse < len(verses) - 1 else ""
    return prev_verse, curr_verse, next_verse

def convert_decimals(obj):
    """
    Recursively convert all Decimal instances to int or float.
    """
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

@app.get("/settings", response_class=HTMLResponse)
def get_settings(request: Request):
    session_id = request.cookies.get("session_id")
    response = settings_table.get_item(Key={"user_id": session_id})
    saved = convert_decimals(response.get("Item", {}))

    selected_books = saved.get("books", [])
    selected_chapters = saved.get("chapters", {})

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "session_id": session_id,
        "ot_books": OT_BOOKS,
        "nt_books": NT_BOOKS,
        "chapter_counts": CHAPTER_COUNTS,
        "selected_books": selected_books,
        "selected_chapters": selected_chapters,
    })

@app.post("/settings", response_class=HTMLResponse)
def save_settings(
    request: Request,
    session_id: str = Form(...),
    selected_books: list[str] = Form([]),
    selected_chapters: list[str] = Form([]),
):
    # Parse "Genesis|1" into { "Genesis": [1] }
    chapter_map = {}
    for val in selected_chapters:
        book, ch = val.split("|")
        ch = int(ch)
        chapter_map.setdefault(book, []).append(ch)

    item = {
        "user_id": session_id,
        "books": selected_books,
        "ot": any(b in OT_BOOKS for b in selected_books),
        "nt": any(b in NT_BOOKS for b in selected_books),
        "chapters": chapter_map,
    }

    settings_table.put_item(Item=item)
    return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/play", response_class=HTMLResponse)
def play(request: Request):
    session_id = request.cookies.get("session_id") or str(uuid6())
    book, chapter, verse = get_random_reference(session_id)
    prev_text, curr_text, next_text = get_surrounding_verses(book, chapter, verse)
    reference = f"{book} {chapter + 1}:{verse + 1}"
    context = {
        "request": request,
        "prev_text": prev_text,
        "curr_text": curr_text,
        "next_text": next_text,
        "reference": reference,
        "session_id": session_id
    }
    response = templates.TemplateResponse("play.html", context)
    response.set_cookie(key="session_id", value=session_id)
    return response

@app.post("/submit", response_class=HTMLResponse)
def submit(
    request: Request,
    submitted_ref: str = Form(...),
    actual_ref: str = Form(...),
    session_id: str = Form(...)
):
    correct = submitted_ref.strip().lower() == actual_ref.strip().lower()
    score = 1 if correct else 0
    context = {
        "request": request,
        "submitted_ref": submitted_ref,
        "actual_ref": actual_ref,
        "score": score
    }
    results_table.put_item(Item={
        "user_id": session_id,
        "id": str(uuid6()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "submitted_ref": submitted_ref,
        "actual_ref": actual_ref,
        "score": score,
    })
    return templates.TemplateResponse("result.html", context)

@app.post("/continue")
def continue_game():
    return RedirectResponse(url="/play", status_code=303)

handler = Mangum(app)