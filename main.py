from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "Cricket score backend is running",
        "endpoints": [
            "/",
            "/live-scores",
            "/debug"
        ]
    })


@app.route("/debug")
def debug():
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(
            CRICBUZZ_URL,
            headers=headers,
            timeout=20
        )

        soup = BeautifulSoup(response.text, "html.parser")

        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "url": response.url,
            "content_length": len(response.text),
            "title": soup.title.get_text(strip=True) if soup.title else None,
            "html_start": response.text[:1000]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/live-scores")
def live_scores():
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(
            CRICBUZZ_URL,
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        matches = []

        # Cricbuzz live-score cards
        selectors = [
            ".cb-mtch-lst",
            ".cb-col.cb-col-100.cb-scrd-itms",
            ".cb-col-100.cb-col"
        ]

        cards = []

        for selector in selectors:
            found = soup.select(selector)
            if found:
                cards.extend(found)

        seen = set()

        for card in cards:
            text = " ".join(card.stripped_strings)

            if not text:
                continue

            key = text[:250]

            if key in seen:
                continue

            seen.add(key)

            # Only keep likely cricket match entries
            cricket_words = [
                "IND", "AUS", "ENG", "PAK",
                "SA", "NZ", "WI", "SL",
                "BAN", "AFG", "IRE", "ZIM",
                "LIVE", "TOSS", "OVERS"
            ]

            if any(word in text.upper() for word in cricket_words):
                matches.append({
                    "text": text[:500]
                })

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
