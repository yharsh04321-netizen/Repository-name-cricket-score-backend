```python
from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
from html import escape

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

selected_match = None


def fetch_matches():
    try:
        response = requests.get(
            CRICBUZZ_URL,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        matches = []

        for index, item in enumerate(
            soup.select(".cb-mtch-lst")
        ):
            text = " ".join(item.stripped_strings)

            if not text:
                continue

            matches.append({
                "id": str(index),
                "name": text
            })

        return matches

    except Exception as error:
        print("Fetch error:", error)
        return []


@app.route("/")
def home():
    return jsonify({
        "service": "Cricket Live Score Backend",
        "status": "online",
        "success": True
    })


@app.route("/live-scores")
def live_scores():
    matches = fetch_matches()

    return jsonify({
        "success": True,
        "count": len(matches),
        "matches": matches
    })


@app.route("/select-match", methods=["GET", "POST"])
def select_match():
    global selected_match

    matches = fetch_matches()

    if request.method == "POST":
        match_id = request.form.get("match_id")

        for match in matches:
            if match["id"] == match_id:
                selected_match = match
                break

    cards = ""

    for match in matches:
        safe_name = escape(match["name"])
        safe_id = escape(match["id"])

        cards += f"""
        <div class="match">

            <div class="live">
                ● LIVE / MATCH
            </div>

            <div class="name">
                {safe_name}
            </div>

            <form method="POST">
                <input
                    type="hidden"
                    name="match_id"
                    value="{safe_id}"
                >

                <button type="submit">
                    SELECT THIS MATCH
                </button>
            </form>

        </div>
        """

    if not cards:
        cards = """
        <div class="empty">
            No matches found right now.
            <br><br>
            Click REFRESH MATCHES.
        </div>
        """

    selected_html = ""

    if selected_match:
        selected_name = escape(selected_match["name"])

        selected_html = f"""
        <div class="selected">

            ✓ SELECTED MATCH

            <br><br>

            <strong>
                {selected_name}
            </strong>

            <br><br>

            OBS SCOREBOARD:

            <br><br>

            <code>
                /scoreboard
            </code>

        </div>
        """

    html = f"""
<!DOCTYPE html>
<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Select Match</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, sans-serif;
}}

.container {{
    max-width: 900px;
    margin: 40px auto;
    padding: 20px;
}}

h1 {{
    font-size: 32px;
    margin-bottom: 8px;
}}

.subtitle {{
    color: #aaa;
    margin-bottom: 25px;
}}

.match {{
    background: #1d1d1d;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
}}

.live {{
    color: #00e676;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 10px;
}}

.name {{
    font-size: 19px;
    font-weight: bold;
    margin-bottom: 18px;
}}

button {{
    background: #00c853;
    color: white;
    border: 0;
    border-radius: 7px;
    padding: 12px 20px;
    font-weight: bold;
    cursor: pointer;
}}

button:hover {{
    background: #00e676;
}}

.refresh {{
    background: #333;
    margin-bottom: 20px;
}}

.refresh:hover {{
```
