from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
from html import escape
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
JINA_URL = "https://r.jina.ai/https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

selected_match = None


def fetch_matches():
    """Fetch match listings from Cricbuzz, with a fallback through Jina Reader."""
    try:
        response = requests.get(
            CRICBUZZ_URL,
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        matches = []

        # Cricbuzz has used several card/container classes over time.
        cards = soup.select(
            ".cb-mtch-lst, .cb-lv-scrs-well, li.cb-match-card"
        )

        for index, item in enumerate(cards):
            title = item.select_one(
                ".cb-lv-scrs-well-top, .cb-mtch-crd-itm-ttl, .text-hvr-underline, h3"
            )

            text = " ".join(item.stripped_strings)
            name = title.get_text(" ", strip=True) if title else text

            if not name or len(name) < 5:
                continue

            # Avoid adding large page containers as individual matches.
            if len(name) > 250:
                continue

            matches.append({
                "id": str(len(matches)),
                "name": name
            })

        if matches:
            return matches

        print("Direct Cricbuzz parser returned no matches; trying Jina fallback...")

    except Exception as error:
        print("Direct Cricbuzz fetch error:", error)

    # Fallback: Jina Reader can return a clean representation when the
    # Render server cannot parse Cricbuzz's normal HTML response.
    try:
        response = requests.get(
            JINA_URL,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=20
        )
        response.raise_for_status()

        matches = []
        seen = set()

        for line in response.text.splitlines():
            line = " ".join(line.split())

            if not line:
                continue

            # Match lines containing the normal Cricbuzz "Team vs Team" form.
            if re.search(r"\bvs\.?\b", line, re.IGNORECASE):
                if len(line) > 220:
                    continue

                # Remove markdown link syntax when present.
                line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
                line = line.strip(" -*|#")

                if line and line not in seen:
                    seen.add(line)
                    matches.append({
                        "id": str(len(matches)),
                        "name": line
                    })

        print("Jina fallback matches:", len(matches))
        return matches

    except Exception as error:
        print("Jina fallback error:", error)
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
        "matches": matches,
        "selected_match": selected_match
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
            <div class="live">● LIVE / MATCH</div>
            <div class="name">{safe_name}</div>
            <form method="POST">
                <input type="hidden" name="match_id" value="{safe_id}">
                <button type="submit">SELECT THIS MATCH</button>
            </form>
        </div>
        """

    if not cards:
        cards = """
        <div class="empty">
            No matches found right now.<br><br>
            Click REFRESH MATCHES.
        </div>
        """

    selected_html = ""

    if selected_match:
        selected_html = f"""
        <div class="selected">
            ✓ SELECTED MATCH
            <br><br>
            <strong>{escape(selected_match["name"])}</strong>
            <br><br>
            OBS scoreboard URL:
            <br><br>
            <code>/scoreboard</code>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Select Match</title>
<style>
body {{ margin: 0; background: #101010; color: white; font-family: Arial, sans-serif; }}
.container {{ max-width: 900px; margin: 40px auto; padding: 20px; }}
h1 {{ font-size: 32px; }}
.subtitle {{ color: #aaa; margin-bottom: 25px; }}
.match {{ background: #1d1d1d; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 15px; }}
.live {{ color: #00e676; font-size: 13px; font-weight: bold; margin-bottom: 10px; }}
.name {{ font-size: 19px; font-weight: bold; margin-bottom: 18px; }}
button {{ background: #00c853; color: white; border: 0; border-radius: 7px; padding: 12px 20px; font-weight: bold; cursor: pointer; }}
button:hover {{ background: #00e676; }}
.refresh {{ background: #333; margin-bottom: 20px; }}
.selected {{ background: #12351f; border: 1px solid #00c853; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
.empty {{ background: #1d1d1d; padding: 30px; text-align: center; color: #aaa; border-radius: 10px; }}
code {{ background: #000; padding: 5px 8px; border-radius: 5px; }}
</style>
</head>
<body>
<div class="container">
<h1>🏏 CRICKET LIVE SCORE</h1>
<div class="subtitle">Select today's match for your OBS scoreboard.</div>
{selected_html}
<button class="refresh" onclick="location.reload()">↻ REFRESH MATCHES</button>
{cards}
</div>
</body>
</html>
"""

    return Response(html, mimetype="text/html")


@app.route("/scoreboard")
def scoreboard():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>OBS Scoreboard</title>
<style>
html, body { margin: 0; padding: 0; width: 100%; height: 100%; background: transparent !important; overflow: hidden; font-family: Arial, sans-serif; }
.scoreboard { position: absolute; left: 20px; bottom: 20px; min-width: 420px; padding: 14px 22px; background: rgba(0, 0, 0, 0.88); color: white; border-radius: 10px; font-weight: bold; }
.live { color: #00e676; font-size: 13px; margin-bottom: 7px; }
.score { font-size: 23px; line-height: 1.35; }
</style>
</head>
<body>
<div class="scoreboard">
    <div class="live">● LIVE CRICKET</div>
    <div id="score" class="score">Loading...</div>
</div>
<script>
async function updateScore() {
    try {
        const response = await fetch('/selected-match?t=' + Date.now(), {cache: 'no-store'});
        const data = await response.json();
        const score = document.getElementById('score');
        score.textContent = data.match ? data.match.name : 'No match selected';
    } catch (error) {
        document.getElementById('score').textContent = 'Score unavailable';
    }
}
updateScore();
setInterval(updateScore, 15000);
</script>
</body>
</html>
"""

    return Response(html, mimetype="text/html")


@app.route("/selected-match")
def selected():
    return jsonify({
        "success": True,
        "match": selected_match
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
