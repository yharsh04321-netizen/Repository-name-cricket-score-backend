from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        matches = []

        # Try current Cricbuzz cards
        cards = soup.select("li.cb-match-card")

        # Fallback
        if not cards:
            cards = soup.select(".cb-mtch-lst")

        if not cards:
            cards = soup.select(".cb-schdl")

        for card in cards:

            text = card.get_text(" ", strip=True)

            if not text:
                continue

            teams = []
            scores = []

            # Team names
            selectors = [
                ".cb-hmscg-tm-name",
                ".cb-hmscg-tm-nm"
            ]

            for selector in selectors:
                for element in card.select(selector):

                    name = element.get_text(" ", strip=True)

                    if name and name not in teams:
                        teams.append(name)

            # Scores
            selectors = [
                ".cb-hmscg-tm-sc",
                ".cb-ovr-flo"
            ]

            for selector in selectors:
                for element in card.select(selector):

                    score = element.get_text(" ", strip=True)

                    if score and score not in scores:
                        scores.append(score)

            # Match status
            status = ""

            for selector in [
                ".cb-mtch-crd-state",
                ".cb-text-live",
                ".cb-text-complete"
            ]:

                element = card.select_one(selector)

                if element:

                    status = element.get_text(
                        " ",
                        strip=True
                    )

                    if status:
                        break

            # Match link
            match_url = ""

            link = card.select_one(
                "a[href*='/live-cricket-scores/']"
            )

            if link:

                match_url = link.get(
                    "href",
                    ""
                )

                if match_url.startswith("/"):
                    match_url = (
                        "https://www.cricbuzz.com"
                        + match_url
                    )

            # Add match
            if teams:

                matches.append({
                    "teams": teams,
                    "scores": scores,
                    "status": status,
                    "url": match_url,
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
