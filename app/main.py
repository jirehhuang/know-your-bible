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

DEBUG_MODE = True

def debug(msg):
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")

debug("🟢 main.py is loading")

# DynamoDB setup
debug("Connecting to DynamoDB tables...")
dynamodb = boto3.resource("dynamodb")
results_table = dynamodb.Table("bible-review-results")
settings_table = dynamodb.Table("bible-review-settings")

# FastAPI app setup
debug("Initializing FastAPI app...")
app = FastAPI()

static_dir = "app/static"
if os.path.exists(static_dir):
    debug(f"Mounting static files from: {static_dir}")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    debug("⚠️ Static directory not found")

templates = Jinja2Templates(directory="app/templates")
debug("Templates loaded from: app/templates")

# Load Bible data
debug("Loading Bible JSON data...")
with open("translations/esv.json") as f:
    BIBLE = json.load(f)
debug("Bible data loaded")

# Get random verse reference
def get_random_reference(session_id):
    debug(f"Fetching settings for session_id={session_id}")
    saved = settings_table.get_item(Key={"user_id": session_id}).get("Item", {})
    selected_books = saved.get("books", list(BIBLE.keys()))
    selected_chapters = saved.get("chapters", {})

    book = random.choice(selected_books)
    debug(f"Random book selected: {book}")

    if book in selected_chapters and selected_chapters[book]:
        chapter = int(random.choice(selected_chapters[book]))
        debug(f"Using selected chapters for {book}: {chapter}")
    else:
        chapter = random.randint(0, len(BIBLE[book]) - 1)
        debug(f"No chapters selected for {book}, picked random: {chapter}")

    chapter = int(chapter)
    verse = random.randint(0, len(BIBLE[book][chapter]) - 1)
    debug(f"Random verse selected: {verse}")

    return book, chapter, verse

def get_surrounding_verses(book, chapter, verse):
    debug(f"Getting verses: {book} {chapter + 1}:{verse + 1}")
    verses = BIBLE[book][chapter]
    prev_verse = verses[verse - 1] if verse > 0 else ""
    curr_verse = verses[verse]
    next_verse = verses[verse + 1] if verse < len(verses) - 1 else ""
    return prev_verse, curr_verse, next_verse

def convert_decimals(obj):
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
    debug(f"[GET] /settings for session_id={session_id}")
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
    debug(f"[POST] /settings - session_id={session_id}")
    debug(f"Selected books: {selected_books}")
    debug(f"Selected chapters (raw): {selected_chapters}")

    chapter_map = {}
    for val in selected_chapters:
        book, ch = val.split("|")
        ch = int(ch)
        chapter_map.setdefault(book, []).append(ch)

    debug(f"Parsed chapter map: {chapter_map}")

    item = {
        "user_id": session_id,
        "books": selected_books,
        "ot": any(b in OT_BOOKS for b in selected_books),
        "nt": any(b in NT_BOOKS for b in selected_books),
        "chapters": chapter_map,
    }

    settings_table.put_item(Item=item)
    debug("Settings saved to DynamoDB")
    return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    debug("[GET] /")
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/play", response_class=HTMLResponse)
def play(request: Request):
    session_id = request.cookies.get("session_id") or str(uuid6())
    debug(f"[GET] /play - session_id={session_id}")
    book, chapter, verse = get_random_reference(session_id)
    prev_text, curr_text, next_text = get_surrounding_verses(book, chapter, verse)
    reference = f"{book} {chapter + 1}:{verse + 1}"
    debug(f"Selected reference: {reference}")

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
    debug(f"[POST] /submit - session_id={session_id}")
    debug(f"Submitted: {submitted_ref}, Actual: {actual_ref}")

    correct = submitted_ref.strip().lower() == actual_ref.strip().lower()
    score = 1 if correct else 0
    debug(f"Score: {score}")

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
    debug("Result saved to DynamoDB")

    return templates.TemplateResponse("result.html", context)

@app.post("/continue")
def continue_game():
    debug("[POST] /continue")
    return RedirectResponse(url="/play", status_code=303)

debug("Creating Mangum handler")
handler = Mangum(app)
debug("✅ handler created successfully")
