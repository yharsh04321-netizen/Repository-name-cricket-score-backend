```python
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import re
import time

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
    "Referer": "https://www.cricbuzz.com/",
}


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.route("/")
def home():
    return jsonify({
        "success": True,
        "service": "Cricket Live Score Backend",
        "status": "online",
        "endpoints": [
            "/live-scores",
            "/debug",
            "/debug-match"
        ]
    })


# ---------------------------------------------------------
# FETCH CRICBUZZ
# ---------------------------------------------------------

def fetch_cricbuzz():
    response = requests.get(
        CRICBUZZ_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    return response.text


# ---------------------------------------------------------
# CLEAN TEXT
# ---------------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------
# SCORE EXTRACTION
# ---------------------------------------------------------

def extract_scores(text):
    """
    Finds cricket scores such as:

    295-7 (50)
    60-0 (8.4)
    187/4
    60/0 (8.4)
    """

    patterns = [
        r"\b\d{1,4}-\d{1,2}\s*\(\d{1,2}(?:\.\d)?\)",
        r"\b\d{1,4}/\d{1,2}\s*\(\d{1,2}(?:\.\d)?\)",
        r"\b\d{1,4}-\d{1,2}\b",
        r"\b\d{1,4}/\d{1,2}\b",
    ]

    found = []

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for value in matches:
            value = clean_text(value)

            if value not in found:
                found.append(value)

    return found


# ---------------------------------------------------------
# MATCH PARSER
# ---------------------------------------------------------

def parse_matches(html):
    soup = BeautifulSoup(html, "html.parser")

    matches = []

    # Remove scripts/styles so we only work with visible page text.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Cricbuzz has several containers around match cards.
    # We inspect common match-related elements first.
    candidates = soup.find_all(
        [
            "div",
            "a",
            "article",
            "li"
        ]
    )

    seen = set()

    for element in candidates:

        text = clean_text(element.get_text(" ", strip=True))

        if len(text) < 20:
            continue

        # A match card normally contains a score, an over,
        # or a match status.
        scores = extract_scores(text)

        interesting = (
            len(scores) > 0
            or "Need " in text
            or "won by" in text
            or "Innings Break" in text
            or "opt to" in text
            or "Stumps" in text
            or "LIVE" in text
        )

        if not interesting:
            continue

        # Avoid huge parent containers containing many matches.
        if len(text) > 700:
            continue

        key = text[:500]

        if key in seen:
            continue

        seen.add(key)

        # Try to find a match URL.
        link = element.find("a", href=True)

        match_url = None

        if link:
            href = link.get("href", "")

            if "cricbuzz.com" in href:
                match_url = href
            elif href.startswith("/"):
                match_url = "https://www.cricbuzz.com" + href

        matches.append({
            "text": text,
            "scores": scores,
            "url": match_url
        })

    return matches


# ---------------------------------------------------------
# BETTER TEXT-BASED MATCH EXTRACTION
# ---------------------------------------------------------

def parse_live_matches(html):
    """
    Secondary parser.

    Cricbuzz's HTML can contain duplicated desktop/mobile/
    navigation versions of the same match. This parser works
    from the visible text and groups likely match lines.
    """

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    results = []

    score_pattern = re.compile(
        r"\b\d{1,4}[-/]\d{1,2}"
        r"(?:\s*\(\d{1,2}(?:\.\d)?\))?"
    )

    status_words = (
        "Need ",
        "won by",
        "Innings Break",
        "opt to",
        "Stumps",
        "LIVE",
        "Match abandoned",
        "Toss delayed"
    )

    for i, line in enumerate(lines):

        has_score = bool(score_pattern.search(line))

        has_status = any(
            word.lower() in line.lower()
            for word in status_words
        )

        if not has_score and not has_status:
            continue

        # Look around the line for nearby team/match information.
        start = max(0, i - 3)
        end = min(len(lines), i + 4)

        context = " ".join(lines[start:end])
        context = clean_text(context)

        if len(context) > 800:
            context = context[:800]

        scores = score_pattern.findall(context)

        if not scores and not has_status:
            continue

        results.append({
            "text": context,
            "scores": list(dict.fromkeys(scores))
        })

    # Remove duplicates.
    unique = []
    seen = set()

    for item in results:
        key = item["text"]

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ---------------------------------------------------------
# LIVE SCORES
# ---------------------------------------------------------

@app.route("/live-scores")
def live_scores():

    try:
        html = fetch_cricbuzz()

        # First parser.
        matches = parse_matches(html)

        # If the first parser doesn't find enough useful data,
        # use the text parser.
        if len(matches) == 0:
            matches = parse_live_matches(html)

        # Remove obviously huge/duplicate entries.
        clean_matches = []

        seen = set()

        for match in matches:

            text = clean_text(match.get("text", ""))

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)

            clean_matches.append({
                "text": text,
                "scores": match.get("scores", []),
                "url": match.get("url")
            })

        return jsonify({
            "success": True,
            "count": len(clean_matches),
            "matches": clean_matches,
            "source": "Cricbuzz",
            "timestamp": int(time.time())
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Cricbuzz request failed",
            "details": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Parser error",
            "details": str(e)
        }), 500


# ---------------------------------------------------------
# DEBUG
# ---------------------------------------------------------

@app.route("/debug")
def debug():

    try:
        html = fetch_cricbuzz()

        return jsonify({
            "success": True,
            "status_code": 200,
            "page_length": len(html),
            "india_found": "India" in html,
            "west_indies_found": "West Indies" in html,
            "score_samples": extract_scores(
                BeautifulSoup(
                    html,
                    "html.parser"
                ).get_text(" ", strip=True)
            )[:30],
            "page_preview": clean_text(
                BeautifulSoup(
                    html,
                    "html.parser"
                ).get_text(" ", strip=True)
            )[:3000]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# DEBUG MATCH
# ---------------------------------------------------------

@app.route("/debug-match")
def debug_match():

    try:
        html = fetch_cricbuzz()

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

            position = html.find(term)

            if position != -1:
                matched_term = term
                break

        if position == -1:

            return jsonify({
                "success": False,
                "message": "Match text not found",
                "page_length": len(html)
            })

        start = max(0, position - 5000)
        end = min(len(html), position + 15000)

        return jsonify({
            "success": True,
            "matched_term": matched_term,
            "position": position,
            "html_length": len(html),
            "section": html[start:end]
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "error": "Cricbuzz request failed",
            "details": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# RUN LOCALLY
# ---------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
```
