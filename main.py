from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
from html import escape
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
JINA_URL = "https://r.jina.ai/https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

selected_match = None


def fetch_matches():
    """Fetch Cricbuzz match cards and fall back to link/text parsing."""
    matches = []
    seen = set()

    def add_match(name, url=""):
        name = " ".join(str(name).split()).strip()
        if not name or len(name) < 5 or len(name) > 250:
            return
        # Do not add huge page headings or navigation text.
        if name.lower() in seen:
            return
        seen.add(name.lower())
        matches.append({
            "id": str(len(matches)),
            "name": name,
            "url": url
        })

    try:
        response = requests.get(CRICBUZZ_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Try known match-card containers first.
        for selector in [
            ".cb-mtch-lst",
            ".cb-lv-scrs-well",
            "li.cb-match-card",
            "div.cb-col.cb-col-100.cb-mtch-lst"
        ]:
            for item in soup.select(selector):
                link = item.select_one('a[href*="/live-cricket-scores/"]')
                text = " ".join(item.stripped_strings)
                url = link.get("href", "") if link else ""
                add_match(text, url)

        # If card classes changed, use the actual live-score links.
        if not matches:
            for link in soup.select('a[href*="/live-cricket-scores/"]'):
                text = " ".join(link.stripped_strings)
                href = link.get("href", "")
                add_match(text, href)

        if matches:
            return matches

        print("Cricbuzz HTML returned no match cards; trying Jina fallback")

    except Exception as error:
        print("Direct Cricbuzz error:", error)

    # Jina Reader fallback. It often exposes Cricbuzz content when the
    # normal HTML response is difficult for a server-side scraper to parse.
    try:
        response = requests.get(
            JINA_URL,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=25
        )
        response.raise_for_status()

        for raw_line in response.text.splitlines():
            line = " ".join(raw_line.split()).strip(" -*|#")
            if not line:
                continue

            # Match lines such as "Team A vs Team B ...".
            if not re.search(r"\bvs\.?\b", line, re.IGNORECASE):
                continue
            if len(line) > 250:
                continue

            line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
            add_match(line)

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
        cards += f"""
        <div class="match">
            <div class="live">● LIVE / MATCH</div>
            <div class="name">{escape(match["name"])}</div>
            <form method="POST">
                <input type="hidden" name="match_id" value="{escape(match["id"])}">
                <button type="submit">SELECT THIS MATCH</button>
            </form>
        </div>
        """

    if not cards:
        cards = """
        <div class="empty">No matches found right now.<br><br>Try REFRESH MATCHES.</div>
        """

    selected_html = ""
    if selected_match:
        selected_html = f"""
        <div class="selected">
            ✓ SELECTED MATCH<br><br>
            <strong>{escape(selected_match["name"])}</strong><br><br>
            OBS scoreboard URL:<br><br>
            <code>/scoreboard</code>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Select Match</title>
<style>
body {{margin:0;background:#101010;color:white;font-family:Arial,sans-serif}}
.container {{max-width:900px;margin:40px auto;padding:20px}}
h1 {{font-size:32px}} .subtitle {{color:#aaa;margin-bottom:25px}}
.match {{background:#1d1d1d;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:15px}}
.live {{color:#00e676;font-size:13px;font-weight:bold;margin-bottom:10px}}
.name {{font-size:19px;font-weight:bold;margin-bottom:18px}}
button {{background:#00c853;color:white;border:0;border-radius:7px;padding:12px 20px;font-weight:bold;cursor:pointer}}
button:hover {{background:#00e676}} .refresh {{background:#333;margin-bottom:20px}}
.selected {{background:#12351f;border:1px solid #00c853;border-radius:10px;padding:20px;margin-bottom:20px}}
.empty {{background:#1d1d1d;padding:30px;text-align:center;color:#aaa;border-radius:10px}}
code {{background:#000;padding:5px 8px;border-radius:5px}}
</style></head><body><div class="container">
<h1>🏏 CRICKET LIVE SCORE</h1>
<div class="subtitle">Select today's match for your OBS scoreboard.</div>
{selected_html}
<button class="refresh" onclick="location.reload()">↻ REFRESH MATCHES</button>
{cards}
</div></body></html>
"""
    return Response(html, mimetype="text/html")


@app.route("/scoreboard")
def scoreboard():
    html = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><title>OBS Scoreboard</title>
<style>
html,body{margin:0;padding:0;width:100%;height:100%;background:transparent!important;overflow:hidden;font-family:Arial,sans-serif}
.scoreboard{position:absolute;left:20px;bottom:20px;min-width:420px;padding:14px 22px;background:rgba(0,0,0,.88);color:white;border-radius:10px;font-weight:bold}
.live{color:#00e676;font-size:13px;margin-bottom:7px}.score{font-size:23px;line-height:1.35}
</style></head><body><div class="scoreboard"><div class="live">● LIVE CRICKET</div><div id="score" class="score">Loading...</div></div>
<script>
async function updateScore(){try{const r=await fetch('/selected-match?t='+Date.now(),{cache:'no-store'});const d=await r.json();document.getElementById('score').textContent=d.match?d.match.name:'No match selected';}catch(e){document.getElementById('score').textContent='Score unavailable';}}
updateScore();setInterval(updateScore,15000);
</script></body></html>
"""
    return Response(html, mimetype="text/html")


@app.route("/selected-match")
def selected():
    return jsonify({"success": True, "match": selected_match})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
