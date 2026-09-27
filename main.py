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


def parse_live_matches(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    score_pattern = re.compile(
        r"\b\d{1,4}[-/]\d{1,2}"
        r"(?:\s*\(\d{1,2}(?:\.\d)?\))?"
    )

    status_words = [
        "Need ",
        "won by",
        "Innings Break",
        "opt to",
        "Stumps",
        "LIVE",
        "Match abandoned",
        "Toss delayed"
    ]

    results = []
    seen = set()

    for i, line in enumerate(lines):

        has_score = bool(score_pattern.search(line))

        has_status = any(
            word.lower() in line.lower()
            for word in status_words
        )

        if not has_score and not has_status:
            continue

        start = max(0, i - 4)
        end = min(len(lines), i + 5)

        context = clean_text(
            " ".join(lines[start:end])
        )

        if len(context) > 1000:
            context = context[:1000]

        scores = score_pattern.findall(context)

        key = context.lower()

        if key in seen:
            continue

        seen.add(key)

        results.append({
            "text": context,
            "scores": list(dict.fromkeys(scores))
        })

    return results


@app.route("/live-scores")
def live_scores():

    try:
        html = fetch_cricbuzz()
        matches = parse_live_matches(html)

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches,
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


@app.route("/debug")
def debug():

    try:
        html = fetch_cricbuzz()

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        page_text = clean_text(
            soup.get_text(" ", strip=True)
        )

        return jsonify({
            "success": True,
            "status_code": 200,
            "page_length": len(html),
            "india_found": "India" in html,
            "west_indies_found": "West Indies" in html,
            "score_samples": extract_scores(page_text)[:30],
            "page_preview": page_text[:3000]
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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
