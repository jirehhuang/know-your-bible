import os
import re
import sys
import logging
import boto3
import random
import app.utils.cache as cache
from boto3.dynamodb.conditions import Key
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone
from uuid6 import uuid6
from decimal import Decimal
from math import floor, log10
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from fsrs import Scheduler, Card, Rating, ReviewLog
from app.utils.bible import get_bible_translation, OT_BOOKS, NT_BOOKS, CHAPTER_COUNTS, AVAIL_TRANSLATIONS

DEBUG_MODE = True  # Global debug mode flag

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

## Ease rating
rating_map = {
    1: "Again",
    2: "Hard",
    3: "Good",
    4: "Easy"
}

def convert_types(data, to="float"):
    """
    Recursively convert all Decimal to float (to='float') or float to Decimal (to='decimal') in a JSON-like structure.
    """
    if isinstance(data, dict):
        return {k: convert_types(v, to) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_types(v, to) for v in data]
    elif to.lower() == "float" and isinstance(data, Decimal):
        return float(data)
    elif to.lower() == "decimal" and isinstance(data, float):
        return Decimal(str(data))  # Use str to preserve precision
    else:
        return data

def load_user_settings_from_db(user_id: str):
    response = settings_table.get_item(Key={"user_id": user_id})
    settings = convert_types(response.get("Item", {}), "float")
    
    testaments = set(settings.get("testaments", []))
    books = set(settings.get("books", []))
    chapters = settings.get("chapters", {})
    translation = settings.get("translation", "esv")  # Default to ESV
    prioritize_frequency = settings.get("prioritize_frequency", True)

    ## Retrieve scheduler
    scheduler_dict = settings.get("scheduler_dict")
    scheduler = Scheduler.from_dict(scheduler_dict) if scheduler_dict else Scheduler()

    ## Load user data (results)
    user_data = []
    try:
        paginator = results_table.meta.client.get_paginator("query")
        page_iterator = paginator.paginate(
            TableName=results_table.name,
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        for page in page_iterator:
            user_data.extend(page.get("Items", []))
    except Exception as e:
        debug(f"⚠️ Error loading user data for {user_id}: {e}")
        user_data = []

    ## Load derived data
    bible = get_bible_translation(translation=translation, bool_counts=prioritize_frequency, user_data=user_data)
    eligible_references = get_eligible_references(bible, testaments, books, chapters)

    ## Cache full user config
    full_settings = {
        "settings": settings,
        "bible": bible,
        "eligible_references": eligible_references,
        "user_data": user_data,
        "scheduler": scheduler,
    }

    cache.set_cached_user_settings(user_id, full_settings)

    return full_settings

def get_eligible_references(bible, selected_testaments, selected_books, selected_chapters):
    ## Add entire testament(s)
    selected_books |= set(OT_BOOKS if "old" in selected_testaments else [])
    selected_books |= set(NT_BOOKS if "new" in selected_testaments else [])
    
    eligible_references = []

    for book in bible:
        chapters = bible[book]
        if book in selected_books:
            for chapter in chapters:
                for verse in chapters[chapter]:
                    eligible_references.append((book, chapter, verse, 1))
        elif book in selected_chapters:
            for ch in selected_chapters[book]:
                ch_str = str(ch)
                if ch_str in chapters:
                    for verse in chapters[ch_str]:
                        eligible_references.append((book, chapter, verse, 1))
                else:
                    debug(f"⚠️ Chapter {ch_str} not found in {book}")

    if not eligible_references:
        debug("⚠️ No eligible references found, falling back to full bible")
        for book in bible:
            for chapter in bible[book]:
                for verse in bible[book][chapter]:
                    eligible_references.append((book, chapter, verse, 1))

    # debug(f"eligible_references: {json.dumps(eligible_references, indent=2)}")
    
    return eligible_references

def update_weights(bible, eligible_references, upweight=["John MacArthur", "John Piper"]):
    now = datetime.now(timezone.utc)

    def get_weight(book, chapter, verse):
        ## Initial weight "prior"
        verse_dict = bible[book][chapter][verse]
        weight = verse_dict.get("weight", 1)

        ## Add counts, if included with bool_counts
        for upweight_key in upweight:
            weight += verse_dict.get(upweight_key, 0)

        ## Adjust by due date, if any
        due = datetime.fromisoformat(verse_dict.get("user_data", {}).get("due_str", now.isoformat()))
        days2due = (now - due).days
        weight_factor = 10 ** min(log10(sys.float_info.max), days2due)
        weight = weight * weight_factor

        return weight
    
    eligible_references = [
        (book, chapter, verse, get_weight(book, chapter, verse)) 
        for (book, chapter, verse, _) in eligible_references
    ]
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
def get_random_reference(settings):

    ## Refresh weights before sampling
    eligible_references = update_weights(settings["bible"], settings["eligible_references"])

    book, chapter, verse, weight = weighted_sample(eligible_references)
    debug(f"Random reference selected: {book} {chapter}:{verse} with weight={weight}")
    return book, chapter, verse

def get_surrounding_verses(bible, book, chapter, verse):
    debug(f"Getting verses surrounding: {book} {chapter}:{verse}")
    chapters = bible[book]
    chapter_keys = sorted(chapters, key=lambda k: int(k))
    curr_verses = chapters[str(chapter)]
    verse_keys = sorted(curr_verses, key=lambda k: int(k))

    def get_text(ch, v):
        try:
            return bible[book][str(ch)][str(v)]["text"]
        except KeyError:
            return ""

    try:
        idx = verse_keys.index(str(verse))
    except ValueError:
        debug("⚠️ Verse not found")
        return "", "", ""

    ## Previous verse logic
    if idx > 0:
        prev_text = get_text(chapter, int(verse_keys[idx - 1]))
    else:
        ## First verse in chapter
        ch_idx = chapter_keys.index(str(chapter))
        if ch_idx > 0:
            prev_ch = chapter_keys[ch_idx - 1]
            prev_ch_verses = chapters[prev_ch]
            prev_verse_keys = sorted(prev_ch_verses, key=lambda k: int(k))
            prev_text = get_text(prev_ch, prev_verse_keys[-1])
        else:
            prev_text = ""

    ## Next verse logic
    if idx < len(verse_keys) - 1:
        next_text = get_text(chapter, int(verse_keys[idx + 1]))
    else:
        ## Last verse in chapter
        ch_idx = chapter_keys.index(str(chapter))
        if ch_idx < len(chapter_keys) - 1:
            next_ch = chapter_keys[ch_idx + 1]
            next_ch_verses = chapters[next_ch]
            next_verse_keys = sorted(next_ch_verses, key=lambda k: int(k))
            next_text = get_text(next_ch, next_verse_keys[0])
        else:
            next_text = ""

    curr_text = get_text(chapter, verse)
    return prev_text, curr_text, next_text

def match_book_name(bible, input_text):
    input_text = input_text.strip().lower()
    matches = [book for book in bible if book.lower().startswith(input_text)]
    match = matches[0] if len(matches) == 1 else None
    if match:
        debug(f"Matched {input_text} to book: {match}")
    return match

def calculate_score(bible, submitted_book, submitted_ch, submitted_v, actual_book, actual_ch, actual_v, timer):
    def flat_index(book, chapter, verse):
        chapters = bible[book]
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

    ## Penalize by distance and timer, with 20-point grace
    penalty_dist = 1 * distance
    penalty_time = 2 * timer
    penalty = penalty_dist + penalty_time

    ## Compute score with buffer for time penalty
    penalty_time_adj = max(0, penalty_time - 20)
    score = max(0, min(100, floor(100 - penalty_dist - penalty_time_adj)))

    ## Compute rating based on penalty: Easy (<= 20), Good (<=40), Hard (<= 60), Again (>60)
    if penalty <= 20:
        rating = 4
    elif penalty <= 40:
        rating = 3
    elif penalty <= 60:
        rating = 2
    else:
        rating = 1
    
    debug(f"Calculated score: {score} (distance: {distance}, timer: {timer}, rating: {rating})")
    return distance, score, rating

def get_user_id(request: Request) -> str:
    user_id = request.cookies.get("user_id")
    if user_id:
        debug(f"Authenticated user: {user_id}")
        return user_id
    
    # new_user_id = str(uuid6())
    new_user_id = str(datetime.now(timezone.utc).isoformat())
    debug(f"Anonymous session: {new_user_id}")
    return new_user_id

def get_user_id_settings(request: Request) -> str:
    user_id = get_user_id(request)
    settings = cache.get_cached_user_settings(user_id) or load_user_settings_from_db(user_id)
    return user_id, settings

@app.middleware("http")
async def add_user_settings(request: Request, call_next):
    user_id, settings = get_user_id_settings(request)
    request.state.settings = settings
    return await call_next(request)

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

    ## Preload and cache user settings
    load_user_settings_from_db(user_id=email)

    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_id")
    return response

@app.get("/settings", response_class=HTMLResponse)
def get_settings(request: Request):
    user_id, settings = get_user_id_settings(request)

    debug(f"[GET] /settings for user_id={user_id}")

    selected_books = settings.get("settings", {}).get("books", [])
    selected_chapters = settings.get("settings", {}).get("chapters", {})
    selected_testaments = settings.get("settings", {}).get("testaments", [])
    selected_translation = settings.get("settings", {}).get("translation", "esv")
    prioritize_frequency = settings.get("settings", {}).get("prioritize_frequency", True)

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user_id": user_id,
        "ot_books": OT_BOOKS,
        "nt_books": NT_BOOKS,
        "chapter_counts": CHAPTER_COUNTS,
        "avail_translations": AVAIL_TRANSLATIONS,
        "selected_translation": selected_translation,
        "prioritize_frequency": prioritize_frequency,
        "selected_books": selected_books,
        "selected_chapters": selected_chapters,
        "selected_testaments": selected_testaments,
    })

@app.post("/settings", response_class=HTMLResponse)
def save_settings(
    request: Request,
    selected_books: list[str] = Form(default=[]),
    selected_chapters: list[str] = Form(default=[]),
    selected_testaments: list[str] = Form(default=[]),
    translation: str = Form(default="esv"),
    prioritize_frequency: str = Form(default=None),  # checkbox returns "on" if checked, else omitted
):
    user_id, settings = get_user_id_settings(request)
    user_data = settings.get("user_data", [])
    scheduler = settings.get("scheduler", Scheduler())

    debug(f"[POST] /settings - user_id={user_id}")
    debug(f"Selected testaments: {selected_testaments}")
    debug(f"Selected books: {selected_books}")
    debug(f"Selected chapters (raw): {selected_chapters}")
    debug(f"Selected translation: {translation}")
    debug(f"Prioritize by frequency: {bool(prioritize_frequency)}")

    chapter_map = {}
    for val in selected_chapters:
        book, ch = val.split("|")
        ch = int(ch)
        chapter_map.setdefault(book, []).append(ch)

    new_settings = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "testaments": selected_testaments,
        "books": selected_books,
        "chapters": chapter_map,
        "translation": translation,
        "prioritize_frequency": bool(prioritize_frequency),
        "scheduler_dict": scheduler.to_dict(),
    }

    if True or "@" in user_id:  # TODO:
        settings_table.put_item(Item=convert_types(new_settings, "Decimal"))
        debug(f"Settings saved to DynamoDB for user_id={user_id}")

    bible = get_bible_translation(
        translation=translation, 
        bool_counts=prioritize_frequency, 
        user_data=user_data
    )
    cache.set_cached_user_settings(user_id, {
        "settings": new_settings,
        "bible": bible,
        "eligible_references": get_eligible_references(bible, selected_testaments, set(selected_books), chapter_map),
        "user_data": user_data,
        "scheduler": scheduler,
    })
    debug(f"Settings saved for user_id={user_id}")

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("user_id", user_id)
    return response

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    debug("[GET] /")
    return templates.TemplateResponse("home.html", {"request": request})

def render_review(request, user_id, book, chapter, verse, start_timer=0, error=None):
    user_id, settings = get_user_id_settings(request)
    bible = settings["bible"]

    prev_text, curr_text, next_text = get_surrounding_verses(bible, book, chapter, verse)
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
        "start_timer": start_timer,
        "user_id": user_id,
        "error": error,
    }

    response = templates.TemplateResponse("review.html", context)
    response.set_cookie(key="user_id", value=user_id)
    return response

@app.get("/review", response_class=HTMLResponse)
def review(request: Request):
    user_id, settings = get_user_id_settings(request)

    debug(f"[GET] /review - user_id={user_id}")

    book, chapter, verse = get_random_reference(settings)

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
    user_id, settings = get_user_id_settings(request)
    bible = settings["bible"]

    debug(f"[POST] /submit - user_id={user_id}")
    debug(f"Submitted: {submitted_ref}, Actual: {actual_ref}")

    ## Convert chapter and verse back to integers
    actual_ch = chapter
    actual_v = verse

    ## Parse submitted reference
    match = re.match(r"^\s*([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)\s*$", submitted_ref)
    if not match:
        debug("❌ Invalid format")
        return render_review(request, user_id, book, actual_ch, actual_v, timer,
                             error=f"Invalid format: '{submitted_ref}'. Please try again (e.g., Gen 1:1).")

    submitted_book_raw, submitted_ch_str, submitted_v_str = match.groups()
    matched_book = match_book_name(bible, submitted_book_raw)
    if not matched_book:
        debug("❌ Invalid or ambiguous book")
        return render_review(request, user_id, book, actual_ch, actual_v, timer,
                             error=f"Unknown or ambiguous book: '{submitted_book_raw}'. Please try again.")

    submitted_ch = submitted_ch_str
    submitted_v = submitted_v_str

    ## Check if book, chapter, and verse exist in bible
    if (
        matched_book not in bible
        or int(submitted_ch) < 1 or int(submitted_ch) > len(bible[matched_book])
        or int(submitted_v) < 1 or int(submitted_v) > len(bible[matched_book][submitted_ch])
    ):
        debug("❌ Reference does not exist in bible data")
        return render_review(request, user_id, book, actual_ch, actual_v, timer,
                             error=f"Reference not found: '{matched_book} {submitted_ch}:{submitted_v}'.")

    normalized_submitted_ref = f"{matched_book} {submitted_ch}:{submitted_v}"
    debug(f"Submitted: {normalized_submitted_ref}")
    debug(f"Actual: {book} {actual_ch}:{actual_v}")
    debug(f"Timer: {timer}s")

    ## Calculate score based on verse distance
    distance, score, rating = calculate_score(bible, matched_book, submitted_ch, submitted_v, book, actual_ch, actual_v, timer)

    ## Retrieve scheduler and card
    scheduler = settings["scheduler"]

    verse_dict = settings["bible"][book][chapter][verse]["user_data"]
    card = verse_dict.get("card")
    if not card:
        ## Attempt to retrieve from dict; otherwise initialize
        card_dict = verse_dict.get("card_dict")
        card = Card.from_dict(card_dict) if card_dict else Card()
    
    ## Review
    card, review_log = scheduler.review_card(card, rating)

    ## Write to DynamoDB if logged in to email
    result = {
        "user_id": user_id,
        "id": str(uuid6()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reference": actual_ref,
        "submitted": normalized_submitted_ref,
        "score": score,
        "distance": Decimal(str(distance)),
        "timer": Decimal(str(round(float(timer), 3))),
        "rating": rating,
        "card_dict": card.to_dict(),
        "due_str": str(card.due),
    }
    if True or "@" in user_id:  # TODO:
        results_table.put_item(Item=convert_types(result, "Decimal"))
        debug("✅ Result saved to DynamoDB")
    
    ## Update user data for verse
    settings["user_data"].append(result)
    settings["bible"][book][chapter][verse]["user_data"] = result | {"card": card}
    cache.set_cached_user_settings(user_id, settings)

    context = {
        "request": request,
        "submitted_ref": normalized_submitted_ref,
        "actual_ref": actual_ref,
        "actual_text": bible[book][str(actual_ch)][str(actual_v)]["text"],
        "score": score,
        "timer": round(float(timer), 1),
        "rating": rating_map.get(rating, "Unknown"),
    }

    return templates.TemplateResponse("result.html", context)

@app.post("/continue")
def continue_game():
    debug("[POST] /continue")
    return RedirectResponse(url="/review", status_code=303)
