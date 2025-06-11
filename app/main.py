import os
import re
import json
import random
import boto3
import logging
from boto3.dynamodb.conditions import Key
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from uuid6 import uuid6
from decimal import Decimal
from math import floor
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from collections import defaultdict
from app.utils.bible import OT_BOOKS, NT_BOOKS, CHAPTER_COUNTS

## Global attribute store
attr = defaultdict(dict)

DEBUG_MODE = True
B = 1  # TODO: Make adjustable parameter

def debug(msg):
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")

debug("🟢 main.py is loading")

## DynamoDB setup
config = Config(".env")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    region = config("AWS_REGION")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    logger.debug("Connected to DynamoDB.")
except Exception as e:
    logger.error("Failed to connect to DynamoDB", exc_info=True)
    raise

debug("Connecting to DynamoDB tables...")
results_table = dynamodb.Table("know-your-bible-results")
settings_table = dynamodb.Table("know-your-bible-settings")

## FastAPI app setup
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

## Set up Google login
app.add_middleware(SessionMiddleware, secret_key="YOUR_RANDOM_SECRET")

oauth = OAuth(config)
oauth.register(
    name='google',
    client_id=config('GOOGLE_CLIENT_ID'),
    client_secret=config('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

## Load Bible data
debug("Loading Bible JSON data...")
with open("translations/esv.json") as f:
    BIBLE = json.load(f)
debug("Bible data loaded")

def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def initialize_user_settings(user_id: str, default_books=None, default_chapters=None):
    """
    Initialize default settings and eligible_references for a new user.
    If settings already exist in the table, does nothing.
    """
    default_books = default_books or []
    default_chapters = default_chapters or {}

    exists = settings_table.get_item(Key={"user_id": user_id}).get("Item")
    if exists:
        debug(f"Settings already exist for user_id={user_id}, skipping initialization")
        return

    item = {
        "user_id": user_id,
        "books": default_books,
        "chapters": default_chapters,
    }

    settings_table.put_item(Item=item)
    attr[user_id]["eligible_references"] = get_eligible_references(set(default_books), default_chapters)
    debug(f"Initialized default settings and cached references for user_id={user_id}")

def get_eligible_references(selected_books, selected_chapters):
    eligible_references = []

    for book in BIBLE:
        chapters = BIBLE[book]
        if book in selected_books:
            for chapter in chapters:
                for verse in chapters[chapter]:
                    weight = chapters[chapter][verse].get("weight", 1)
                    eligible_references.append((book, chapter, verse, weight))
        elif book in selected_chapters:
            for ch in selected_chapters[book]:
                ch_str = str(ch)
                if ch_str in chapters:
                    for verse in chapters[ch_str]:
                        weight = chapters[ch_str][verse].get("weight", 1)
                        eligible_references.append((book, ch_str, verse, weight))
                else:
                    debug(f"⚠️ Chapter {ch_str} not found in {book}")

    if not eligible_references:
        debug("⚠️ No eligible references found, falling back to full Bible")
        for book in BIBLE:
            for chapter in BIBLE[book]:
                for verse in BIBLE[book][chapter]:
                    weight = BIBLE[book][chapter][verse].get("weight", 1)
                    eligible_references.append((book, chapter, verse, weight))

    # debug(f"eligible_references: {json.dumps(eligible_references, indent=2)}")
    
    return eligible_references

## Weighted sampling helper
def weighted_sample(choices):
    total_weight = sum(w for _, _, _, w in choices)
    r = random.uniform(0, total_weight)
    upto = 0
    for book, ch, v, w in choices:
        upto += w
        if upto >= r:
            return book, ch, v, w
    ## Fallback to last item in case of rounding issues
    return choices[-1]

## Get random verse reference using weights
def get_random_reference(user_id):
    ## Ensure attr entry exists
    if user_id not in attr:
        attr[user_id] = {}

    ## If not cached, load settings and generate
    if "eligible_references" not in attr[user_id]:
        debug(f"Loading settings for user_id={user_id}")
        response = settings_table.get_item(Key={"user_id": user_id})
        saved = response.get("Item")

        if saved:
            selected_books = set(saved.get("books", []))
            selected_chapters = saved.get("chapters", {})
        else:
            debug(f"No settings found for user_id={user_id}, initializing defaults")
            selected_books = set()
            selected_chapters = {}

        attr[user_id]["eligible_references"] = get_eligible_references(selected_books, selected_chapters)

    eligible_references = attr[user_id]["eligible_references"]
    book, chapter, verse, weight = weighted_sample(eligible_references)
    debug(f"Random reference selected: {book} {chapter}:{verse} with weight={weight}")

    return book, chapter, verse

def get_surrounding_verses(book, chapter, verse):
    debug(f"Getting verses surrounding: {book} {chapter}:{verse}")
    chapters = BIBLE[book]
    chapter_keys = sorted(chapters, key=lambda k: int(k))
    curr_verses = chapters[str(chapter)]
    verse_keys = sorted(curr_verses, key=lambda k: int(k))

    def get_text(ch, v):
        try:
            return BIBLE[book][str(ch)][str(v)]["text"]
        except KeyError:
            return ""

    try:
        idx = verse_keys.index(str(verse))
    except ValueError:
        debug("⚠️ Verse not found")
        return "", "", ""

    prev_text = get_text(chapter, int(verse_keys[idx - 1])) if idx > 0 else ""
    next_text = get_text(chapter, int(verse_keys[idx + 1])) if idx < len(verse_keys) - 1 else ""

    curr_text = get_text(chapter, verse)
    return prev_text, curr_text, next_text

def match_book_name(input_text):
    input_text = input_text.strip().lower()
    matches = [book for book in BIBLE if book.lower().startswith(input_text)]
    match = matches[0] if len(matches) == 1 else None
    if match:
        debug(f"Matched {input_text} to book: {match}")
    return match

def calculate_score(submitted_book, submitted_ch, submitted_v, actual_book, actual_ch, actual_v):
    def flat_index(book, chapter, verse):
        chapters = BIBLE[book]
        total = 0
        for ch in sorted(chapters, key=lambda x: int(x)):
            if int(ch) < int(chapter):
                total += len(chapters[ch])
            elif int(ch) == int(chapter):
                for v in sorted(chapters[ch], key=lambda x: int(x)):
                    if int(v) < int(verse):
                        total += 1
        return total

    idx_sub = flat_index(submitted_book, submitted_ch, submitted_v)
    idx_act = flat_index(actual_book, actual_ch, actual_v)
    distance = abs(idx_sub - idx_act)
    score = max(0, floor(100 - B * distance))
    debug(f"Calculated score: {score} (distance: {distance})")
    return distance, score

def get_user_id(request: Request) -> str:
    user_id = request.cookies.get("user_id")
    if user_id:
        debug(f"Authenticated user: {user_id}")
        return user_id
    
    new_user_id = str(uuid6())
    debug(f"Anonymous session: {new_user_id}")
    return new_user_id

@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth")
async def auth(request: Request):
    token = await oauth.google.authorize_access_token(request)

    try:
        user_info = await oauth.google.parse_id_token(request, token)
    except Exception as e:
        debug(f"parse_id_token failed: {e}")
        user_info = await oauth.google.userinfo(token=token)

    email = user_info['email']
    response = RedirectResponse(url="/")
    response.set_cookie("user_id", email)

    ## Initialize user settings if not already present
    initialize_user_settings(user_id=email)

    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_id")
    return response

@app.get("/settings", response_class=HTMLResponse)
def get_settings(request: Request):
    user_id = get_user_id(request)
    debug(f"[GET] /settings for user_id={user_id}")
    response = settings_table.get_item(Key={"user_id": user_id})
    saved = convert_decimals(response.get("Item", {}))

    selected_books = saved.get("books", [])
    selected_chapters = saved.get("chapters", {})

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user_id": user_id,
        "ot_books": OT_BOOKS,
        "nt_books": NT_BOOKS,
        "chapter_counts": CHAPTER_COUNTS,
        "selected_books": selected_books,
        "selected_chapters": selected_chapters,
    })

@app.post("/settings", response_class=HTMLResponse)
def save_settings(
    request: Request,
    selected_books: list[str] = Form([]),
    selected_chapters: list[str] = Form([]),
):
    user_id = get_user_id(request)
    debug(f"[POST] /settings - user_id={user_id}")
    debug(f"Selected books: {selected_books}")
    debug(f"Selected chapters (raw): {selected_chapters}")

    chapter_map = {}
    for val in selected_chapters:
        book, ch = val.split("|")
        ch = int(ch)
        chapter_map.setdefault(book, []).append(ch)

    debug(f"Parsed chapter map: {chapter_map}")

    if user_id:
        ## Save new settings
        item = {
            "user_id": user_id,
            "books": selected_books,
            "chapters": chapter_map,
        }
        settings_table.put_item(Item=item)
        debug(f"Settings saved for user_id={user_id}")

        ## Ensure attr entry exists
        if user_id not in attr:
            attr[user_id] = {}

        ## Cache new eligible references
        attr[user_id]["eligible_references"] = get_eligible_references(set(selected_books), chapter_map)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("user_id", user_id)
    return response

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    debug("[GET] /")
    return templates.TemplateResponse("home.html", {"request": request})

def render_review(request, user_id, book, chapter, verse, error=None):
    prev_text, curr_text, next_text = get_surrounding_verses(book, chapter, verse)
    reference = f"{book} {chapter}:{verse}"

    context = {
        "request": request,
        "prev_text": prev_text,
        "curr_text": curr_text,
        "next_text": next_text,
        "reference": reference,
        "book": book,
        "chapter": chapter,
        "verse": verse,
        "user_id": user_id,
        "error": error,
    }

    response = templates.TemplateResponse("review.html", context)
    response.set_cookie(key="user_id", value=user_id)
    return response

@app.get("/review", response_class=HTMLResponse)
def review(request: Request):
    user_id = get_user_id(request)
    debug(f"[GET] /review - user_id={user_id}")
    book, chapter, verse = get_random_reference(user_id)
    return render_review(request, user_id, book, chapter, verse)

@app.post("/submit", response_class=HTMLResponse)
def submit(
    request: Request,
    submitted_ref: str = Form(...),
    actual_ref: str = Form(...),
    book: str = Form(...),
    chapter: str = Form(...),
    verse: str = Form(...),
    timer: float = Form(0.0)
):
    user_id = get_user_id(request)
    debug(f"[POST] /submit - user_id={user_id}")
    debug(f"Submitted: {submitted_ref}, Actual: {actual_ref}")

    ## Convert chapter and verse back to integers
    actual_ch = chapter
    actual_v = verse

    ## Parse submitted reference
    match = re.match(r"^\s*([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)\s*$", submitted_ref)
    if not match:
        debug("❌ Invalid format")
        return render_review(request, user_id, book, actual_ch, actual_v,
                           error=f"Invalid format: '{submitted_ref}'. Please try again (e.g., Gen 1:1).")

    submitted_book_raw, submitted_ch_str, submitted_v_str = match.groups()
    matched_book = match_book_name(submitted_book_raw)
    if not matched_book:
        debug("❌ Invalid or ambiguous book")
        return render_review(request, user_id, book, actual_ch, actual_v,
                           error=f"Unknown or ambiguous book: '{submitted_book_raw}'. Please try again.")

    submitted_ch = submitted_ch_str
    submitted_v = submitted_v_str

    ## Check if book, chapter, and verse exist in BIBLE
    if (
        matched_book not in BIBLE
        or int(submitted_ch) < 1 or int(submitted_ch) > len(BIBLE[matched_book])
        or int(submitted_v) < 1 or int(submitted_v) > len(BIBLE[matched_book][submitted_ch])
    ):
        debug("❌ Reference does not exist in BIBLE data")
        return render_review(request, user_id, book, actual_ch, actual_v,
                           error=f"Reference not found: '{matched_book} {submitted_ch}:{submitted_v}'.")

    normalized_submitted_ref = f"{matched_book} {submitted_ch}:{submitted_v}"
    debug(f"Submitted: {normalized_submitted_ref}")
    debug(f"Actual: {book} {actual_ch}:{actual_v}")
    debug(f"Timer: {timer}s")

    ## Calculate score based on verse distance
    distance, score = calculate_score(matched_book, submitted_ch, submitted_v, book, actual_ch, actual_v)

    ## Write to DynamoDB if logged in
    if user_id:

        results_table.put_item(Item={
            "user_id": user_id,
            "id": str(uuid6()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reference": actual_ref,
            "submitted": normalized_submitted_ref,
            "score": score,
            "distance": Decimal(str(distance)),
            "timer": Decimal(str(round(float(timer), 3))),
        })
        debug("✅ Result saved to DynamoDB")

    context = {
        "request": request,
        "submitted_ref": normalized_submitted_ref,
        "actual_ref": actual_ref,
        "actual_text": BIBLE[book][str(actual_ch)][str(actual_v)]["text"],
        "score": score,
        "timer": round(float(timer), 1),
    }

    return templates.TemplateResponse("result.html", context)

@app.post("/continue")
def continue_game():
    debug("[POST] /continue")
    return RedirectResponse(url="/review", status_code=303)
