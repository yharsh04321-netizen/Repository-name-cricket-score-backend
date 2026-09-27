from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


@app.route("/")
def home():
    return jsonify({
        "message": "Cricket Score Backend is running",
        "status": "online"
    })


@app.route("/live")
def live_scores():
    url = "https://www.cricbuzz.com/cricket-match/live-scores"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        matches = []

        # Cricbuzz match cards
        cards = soup.select("div.cb-mtch-lst")

        for card in cards:
            text = card.get_text(" ", strip=True)

            if not text:
                continue

            teams = []
            scores = []

            for team in card.select(".cb-hmscg-tm-nm"):
                name = team.get_text(" ", strip=True)
                if name:
                    teams.append(name)

            for score in card.select(".cb-hmscg-tm-sc"):
                value = score.get_text(" ", strip=True)
                if value:
                    scores.append(value)

            status = ""

            status_element = card.select_one(".cb-text-live")
            if status_element:
                status = status_element.get_text(" ", strip=True)

            if not status:
                status_element = card.select_one(".cb-text-complete")
                if status_element:
                    status = status_element.get_text(" ", strip=True)

            if teams:
                matches.append({
                    "teams": teams,
                    "scores": scores,
                    "status": status,
                    "raw": text
                })

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "matches": []
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
