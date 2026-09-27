from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cricbuzz.com/",
}


CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"


@app.route("/")
def home():
    return jsonify({
        "message": "Cricket Score Backend is running",
        "status": "online"
    })


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def get_match_cards(soup):
    """
    Cricbuzz changes CSS classes regularly.
    Try several known containers.
    """

    selectors = [
        "div.cb-mtch-lst",
        "li.cb-match-card",
        "div.cb-col.cb-col-100.cb-scrd-itms",
        "div.cb-col-100.cb-col",
        "div[class*='match-card']",
        "div[class*='match']",
    ]

    cards = []

    for selector in selectors:
        found = soup.select(selector)

        if found:
            cards.extend(found)

    # Remove duplicates
    unique = []
    seen = set()

    for card in cards:
        text = clean_text(card.get_text(" ", strip=True))

        if not text:
            continue

        if text in seen:
            continue

        seen.add(text)
        unique.append(card)

    return unique


def extract_match(card):
    text = clean_text(card.get_text(" ", strip=True))

    lower = text.lower()

    # We are interested in India vs West Indies.
    india_found = (
        "india" in lower
        or "ind" in lower
    )

    west_indies_found = (
        "west indies" in lower
        or "wi" in lower
        or "windies" in lower
    )

    if not (india_found and west_indies_found):
        return None

    teams = []

    # Try known team-name selectors
    team_selectors = [
        ".cb-hmscg-tm-nm",
        ".cb-hmscg-tm-name",
        "[class*='tm-nm']",
        "[class*='team-name']",
    ]

    for selector in team_selectors:
        for element in card.select(selector):
            name = clean_text(element.get_text(" ", strip=True))

            if name and name not in teams:
                teams.append(name)

    # Scores
    scores = []

    score_selectors = [
        ".cb-hmscg-tm-sc",
        "[class*='tm-sc']",
        "[class*='score']",
    ]

    for selector in score_selectors:
        for element in card.select(selector):
            value = clean_text(element.get_text(" ", strip=True))

            if value and value not in scores:
                scores.append(value)

    # Status
    status = ""

    status_selectors = [
        ".cb-text-live",
        ".cb-text-complete",
        ".cb-mtch-crd-state",
        "[class*='state']",
        "[class*='status']",
    ]

    for selector in status_selectors:
        element = card.select_one(selector)

        if element:
            value = clean_text(element.get_text(" ", strip=True))

            if value:
                status = value
                break

    # Match URL
    match_url = ""

    link = card.select_one("a[href]")

    if link:
        href = link.get("href", "")

        if href.startswith("/"):
            match_url = "https://www.cricbuzz.com" + href
        elif href.startswith("http"):
            match_url = href

    return {
        "teams": teams,
        "scores": scores,
        "status": status,
        "url": match_url,
        "raw": text
    }


@app.route("/live")
def live_scores():

    try:
        response = requests.get(
            CRICBUZZ_URL,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        matches = []

        cards = get_match_cards(soup)

        for card in cards:

            match = extract_match(card)

            if match:
                matches.append(match)

        return jsonify({
            "success": True,
            "source": "cricbuzz",
            "count": len(matches),
            "matches": matches
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "error": f"Request error: {str(e)}",
            "matches": []
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e),
            "matches": []
        }), 500


@app.route("/debug")
def debug():

    try:

        response = requests.get(
            CRICBUZZ_URL,
            headers=HEADERS,
            timeout=20
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        text = clean_text(
            soup.get_text(" ", strip=True)
        )

        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "page_length": len(response.text),
            "india_found": "india" in text.lower(),
            "west_indies_found": (
                "west indies" in text.lower()
                or "windies" in text.lower()
            ),
            "page_preview": text[:3000]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
