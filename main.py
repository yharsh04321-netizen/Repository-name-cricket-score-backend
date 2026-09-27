```python
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


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def fetch_cricbuzz():
    response = requests.get(
        CRICBUZZ_URL,
        headers=HEADERS,
        timeout=20
    )
    response.raise_for_status()
    return response.text


def parse_score(value):
    match = re.match(
        r"^(\d{1,4})-(\d{1,2})(?:\s*\((\d{1,2}(?:\.\d)?)\))?$",
        value
    )

    if not match:
        return None

    return {
        "display": value,
        "runs": int(match.group(1)),
        "wickets": int(match.group(2)),
        "overs": match.group(3)
    }


def parse_live_matches(page_html):
    soup = BeautifulSoup(page_html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    lines = []

    for line in soup.get_text("\n").splitlines():
        line = clean_text(line)
        if line:
            lines.append(line)

    score_pattern = re.compile(
        r"\b\d{1,4}-\d{1,2}"
        r"(?:\s*\(\d{1,2}(?:\.\d)?\))?"
    )

    matches = []
    seen = set()

    for index, line in enumerate(lines):

        if not score_pattern.search(line):
            continue

        start = max(0, index - 3)
        end = min(len(lines), index + 4)

        context = clean_text(
            " ".join(lines[start:end])
        )

        if len(context) > 1000:
            context = context[:1000]

        score_strings = list(dict.fromkeys(
            score_pattern.findall(context)
        ))

        scores = []

        for value in score_strings:
            parsed = parse_score(value)

            if parsed:
                scores.append(parsed)

        if not scores:
            continue

        status = ""

        status_rules = [
            r"need\s+\d+\s+runs?",
            r"won\s+by\s+\d+\s+\w+",
            r"innings\s+break",
            r"opt\s+to\s+(?:bat|bowl)",
            r"stumps",
            r"match\s+abandoned",
            r"toss\s+delayed[^|]*",
            r"match\s+delayed[^|]*"
        ]

        for rule in status_rules:
            found = re.search(
                rule,
                context,
                re.IGNORECASE
            )

            if found:
                status = clean_text(found.group(0))
                break

        key = (
            tuple(score["display"] for score in scores),
            status.lower(),
            context[:250].lower()
        )

        if key in seen:
            continue

        seen.add(key)

        matches.append({
            "text": context,
            "scores": scores,
            "status": status
        })

    return matches


def get_live_matches():
    page = fetch_cricbuzz()
    return parse_live_matches(page)


def select_main_match(matches):
    if not matches:
        return None

    preferred_words = [
        "india",
        "ind ",
        "west indies",
        "wi ",
        "south africa",
        "australia",
        "england",
        "sri lanka"
    ]

    for match in matches:
        text = match.get("text", "").lower()

        for word in preferred_words:
            if word in text:
                return match

    return matches[0]


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


@app.route("/live-scores")
def live_scores():
    try:
        matches = get_live_matches()

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches,
            "source": "Cricbuzz",
            "timestamp": int(time.time())
        })

    except requests.RequestException as error:
        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Cricbuzz request failed",
            "details": str(error)
        }), 502

    except Exception as error:
        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Parser error",
            "details": str(error)
        }), 500


@app.route("/scoreboard")
def scoreboard():
    try:
        matches = get_live_matches()
        match = select_main_match(matches)

        if not match:
            return Response(
                "<html><body style='background:transparent;color:white;"
                "font-family:Arial'>No live match found</body></html>",
                mimetype="text/html"
            )

        match_text = html_lib.escape(
            match.get("text", "Live Cricket")
        )

        status = html_lib.escape(
            match.get("status", "")
        )

        scores = match.get("scores", [])

        score1 = ""
        score2 = ""

        if len(scores) >= 1:
            score1 = html_lib.escape(
                scores[0].get("display", "")
            )

        if len(scores) >= 2:
            score2 = html_lib.escape(
                scores[1].get("display", "")
            )

        html_page = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="30">

<style>

html, body {{
    margin: 0;
    padding: 0;
    background: transparent;
    overflow: hidden;
}}

.scoreboard {{
    position: fixed;
    left: 25px;
    right: 25px;
    bottom: 25px;

    padding: 18px 25px;

    background: rgba(8, 12, 20, 0.96);

    border: 2px solid rgba(255,255,255,0.18);

    border-radius: 14px;

    color: white;

    font-family: Arial, Helvetica, sans-serif;

    box-shadow: 0 8px 30px rgba(0,0,0,0.45);
}}

.header {{
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 8px;
}}

.live {{
    display: inline-block;

    margin-left: 10px;

    padding: 5px 9px;

    background: #d71920;

    border-radius: 15px;

    font-size: 12px;
}}

.match {{
    font-size: 17px;

    color: #d8dee9;

    margin-bottom: 14px;
}}

.scores {{
    display: flex;

    align-items: center;

    gap: 35px;

    flex-wrap: wrap;
}}

.score {{
    font-size: 34px;

    font-weight: 800;
}}

.status {{
    font-size: 19px;

    font-weight: bold;

    color: #ffd54a;
}}

.footer {{
    margin-top: 10px;

    font-size: 11px;

    color: #9aa4b2;
}}

</style>
</head>

<body>

<div class="scoreboard">

    <div class="header">
        CRICKET LIVE SCORE
        <span class="live">LIVE</span>
    </div>

    <div class="match">
        {match_text}
    </div>

    <div class="scores">

        <div class="score">
            {score1}
        </div>

        <div class="score">
            {score2}
        </div>

        <div class="status">
            {status}
        </div>

    </div>

    <div class="footer">
        Cricbuzz • Auto refresh 30 seconds
    </div>

</div>

</body>
</html>
"""

        return Response(
            html_page,
            mimetype="text/html"
        )

    except requests.RequestException as error:
        return Response(
            "<html><body style='background:transparent;color:white;"
            "font-family:Arial'>"
            "Score source temporarily unavailable"
            "</body></html>",
            mimetype="text/html"
        )

    except Exception as error:
        return Response(
            "<html><body style='background:transparent;color:white;"
            "font-family:Arial'>"
            "Scoreboard temporarily unavailable"
            "</body></html>",
            mimetype="text/html"
        )


@app.route("/debug")
def debug():
    try:
        page = fetch_cricbuzz()

        soup = BeautifulSoup(page, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = clean_text(
            soup.get_text(" ", strip=True)
        )

        score_pattern = re.compile(
            r"\b\d{1,4}-\d{1,2}"
            r"(?:\s*\(\d{1,2}(?:\.\d)?\))?"
        )

        scores = list(dict.fromkeys(
            score_pattern.findall(text)
        ))

        return jsonify({
            "success": True,
            "status_code": 200,
            "page_length": len(page),
            "india_found": "India" in page,
            "west_indies_found": "West Indies" in page,
            "score_samples": scores[:30],
            "page_preview": text[:3000]
        })

    except requests.RequestException as error:
        return jsonify({
            "success": False,
            "error": "Cricbuzz request failed",
            "details": str(error)
        }), 502

    except Exception as error:
        return jsonify({
            "success": False,
            "error": "Debug error",
            "details": str(error)
        }), 500


@app.route("/debug-match")
def debug_match():
    try:
        page = fetch_cricbuzz()

        search_terms = [
            "West Indies tour of India",
            "West Indies",
            "India need",
            "WI",
            "IND"
        ]

        position = -1
        matched_term = None

        for term in search_terms:
            position = page.find(term)

            if position != -1:
                matched_term = term
                break

        if position == -1:
            return jsonify({
                "success": False,
                "message": "Match text not found",
                "page_length": len(page)
            })

        start = max(0, position - 5000)
        end = min(len(page), position + 15000)

        return jsonify({
            "success": True,
            "matched_term": matched_term,
            "position": position,
            "html_length": len(page),
            "section": page[start:end]
        })

    except requests.RequestException as error:
        return jsonify({
            "success": False,
            "error": "Cricbuzz request failed",
            "details": str(error)
        }), 502

    except Exception as error:
        return jsonify({
            "success": False,
            "error": "Debug error",
            "details": str(error)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
```
