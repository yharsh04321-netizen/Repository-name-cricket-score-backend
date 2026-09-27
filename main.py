from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import time
import html as html_lib

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cricbuzz.com/"
}


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "service": "Cricket Live Score Backend",
        "status": "online",
        "endpoints": [
            "/live-scores",
            "/scoreboard",
            "/debug",
            "/debug-match"
        ]
    })


def fetch_cricbuzz():
    response = requests.get(
        CRICBUZZ_URL,
        headers=HEADERS,
        timeout=20
    )
    response.raise_for_status()
    return response.text


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_scores(text):
    patterns = [
        r"\b\d{1,4}-\d{1,2}\s*\(\d{1,2}(?:\.\d)?\)",
        r"\b\d{1,4}/\d{1,2}\s*\(\d{1,2}(?:\.\d)?\)",
        r"\b\d{1,4}-\d{1,2}\b",
        r"\b\d{1,4}/\d{1,2}\b"
    ]

    found = []

    for pattern in patterns:
        for value in re.findall(pattern, text):
            value = clean_text(value)

            if value not in found:
                found.append(value)

    return found


def parse_score(value):
    match = re.match(
        r"^(\d{1,4})-(\d{1,2})(?:\s*\((\d{1,2}(?:\.\d)?)\))?$",
        value
    )

    if not match:
        return None

    return {
        "runs": int(match.group(1)),
        "wickets": int(match.group(2)),
        "overs": match.group(3)
    }


def parse_live_matches(page_html):
    soup = BeautifulSoup(page_html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    score_pattern = re.compile(
        r"\b\d{1,4}-\d{1,2}"
        r"(?:\s*\(\d{1,2}(?:\.\d)?\))?"
    )

    status_patterns = [
        r"need\s+\d+\s+runs?",
        r"won\s+by\s+[^|]+",
        r"innings\s+break",
        r"opt\s+to\s+(?:bat|bowl)",
        r"stumps",
        r"live",
        r"match\s+abandoned",
        r"toss\s+delayed[^|]*"
    ]

    matches = []
    seen = set()

    for i, line in enumerate(lines):

        if not score_pattern.search(line):
            continue

        start = max(0, i - 3)
        end = min(len(lines), i + 4)

        context = clean_text(
            " ".join(lines[start:end])
        )

        if len(context) > 1200:
            context = context[:1200]

        scores = list(dict.fromkeys(
            score_pattern.findall(context)
        ))

        if not scores:
            continue

        parsed_scores = []

        for score in scores:
            parsed = parse_score(score)

            if parsed:
                parsed_scores.append({
                    "display": score,
                    **parsed
                })

        status = ""

        for pattern in status_patterns:
            status_match = re.search(
                pattern,
                context,
                re.IGNORECASE
            )

            if status_match:
                status = clean_text(status_match.group(0))
                break

        key = (
            tuple(x["display"] for x in parsed_scores),
            status.lower(),
            context[:250].lower()
        )

        if key in seen:
            continue

        seen.add(key)

        matches.append({
            "text": context,
            "scores": parsed_scores,
            "status": status
        })

    return matches


@app.route("/live-scores")
def live_scores():

    try:
        page = fetch_cricbuzz()
        matches = parse_live_matches(page)

       
