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
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        matches = []

        for item in soup.select(
            ".cb-mtch-lst, .cb-mtch-card"
        ):

            text = item.get_text(
                " ",
                strip=True
            )

            if text:
                matches.append(text)

        return jsonify({
            "success": True,
            "matches": matches
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
