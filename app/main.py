import random
import json
import uuid
import boto3
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from uuid6 import uuid6

dynamodb = boto3.resource("dynamodb")
results_table = dynamodb.Table("bible-review-results")


app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

## Load verse data on startup
with open("translations/esv.json") as f:
    BIBLE = json.load(f)

## Helper to get a random verse reference
def get_random_reference():
    book = random.choice(list(BIBLE.keys()))
    chapter = random.randint(0, len(BIBLE[book]) - 1)
    verses = BIBLE[book][chapter]
    verse = random.randint(0, len(verses) - 1)
    return book, chapter, verse

## Helper to get surrounding verses
def get_surrounding_verses(book, chapter, verse):
    verses = BIBLE[book][chapter]
    prev_verse = verses[verse - 1] if verse > 0 else ""
    curr_verse = verses[verse]
    next_verse = verses[verse + 1] if verse < len(verses) - 1 else ""
    return prev_verse, curr_verse, next_verse

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/play", response_class=HTMLResponse)
def play(request: Request):
    book, chapter, verse = get_random_reference()
    prev_text, curr_text, next_text = get_surrounding_verses(book, chapter, verse)
    reference = f"{book} {chapter + 1}:{verse + 1}"
    session_id = request.cookies.get("session_id") or str(uuid.uuid4())
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
