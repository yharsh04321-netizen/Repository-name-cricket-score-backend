from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "message": "Cricket Score Backend is running"
    })


@app.route("/live")
def live():
    try:
        url = "https://www.cricbuzz.com/cricket-match/live-scores"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        matches = []

        # Try Cricbuzz match cards
        selectors = [
            ".cb-mtch-lst",
            ".cb-mtch-card",
            ".cb-col.cb-col-100.cb-scrd-itms",
            "[class*='match']"
        ]

        for selector in selectors:
            for item in soup.select(selector):
                text = item.get_text(
                    " ",
                    strip=True
                )

                if text and len(text) > 10:
                    if text not in matches:
                        matches.append(text)

        # Backup: find useful text from page
        if not matches:
            for item in soup.find_all(["div", "a"]):
                text = item.get_text(
                    " ",
                    strip=True
                )

                if (
                    text
                    and len(text) > 20
                    and (
                        "vs" in text.lower()
                        or "live" in text.lower()
                        or "score" in text.lower()
                    )
                ):
                    if text not in matches:
                        matches.append(text)

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches[:50]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
