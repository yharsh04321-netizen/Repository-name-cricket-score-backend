from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
import re
import html

app = Flask(name)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
}

# Selected match for OBS

selected_match = {
"id": None,
"name": None,
"details": None
}

def fetch_live_scores():
try:
response = requests.get(
CRICBUZZ_URL,
headers=HEADERS,
timeout=15
)

```
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    matches = []

    # Cricbuzz match cards
    items = soup.select(".cb-mtch-lst")

    for index, item in enumerate(items):
        text = " ".join(item.stripped_strings)

        if not text:
            continue

        # Try to find a match URL
        link = item.select_one("a[href*='/live-cricket-scores/']")

        match_url = ""
        if link:
            match_url = link.get("href", "")

        if match_url.startswith("/"):
            match_url = "https://www.cricbuzz.com" + match_url

        # Generate an ID
        match_id = str(index)

        id_match = re.search(r"(\d{5,})", match_url)
        if id_match:
            match_id = id_match.group(1)

        matches.append({
            "id": match_id,
            "name": text,
            "url": match_url
        })

    return {
        "success": True,
        "matches": matches,
        "count": len(matches)
    }

except Exception as error:
    return {
        "success": False,
        "matches": [],
        "count": 0,
        "error": str(error)
    }
```

@app.route("/")
def home():
return jsonify({
"service": "Cricket Live Score Backend",
"status": "online",
"success": True
})

@app.route("/live-scores")
def live_scores():
return jsonify(fetch_live_scores())

@app.route("/select-match")
def select_match():
data = fetch_live_scores()

```
matches = data.get("matches", [])

match_html = ""

if not matches:
    match_html = """
    <div class="empty">
        No live or today's matches were found.
        <br><br>
        Try refreshing this page.
    </div>
    """

else:
    for match in matches:
        match_id = html.escape(str(match["id"]))
        match_name = html.escape(match["name"])

        match_html += f"""
        <div class="match">
            <div class="status">● LIVE / MATCH</div>

            <div class="match-name">
                {match_name}
            </div>

            <form action="/select-match" method="post">
                <input type="hidden" name="match_id" value="{match_id}">
                <button type="submit">
                    SELECT THIS MATCH
                </button>
            </form>
        </div>
        """

selected = ""

if selected_match["id"]:
    selected = f"""
    <div class="selected">
        ✓ SELECTED MATCH
        <br>
        <strong>{html.escape(str(selected_match["name"]))}</strong>
        <br><br>
        OBS URL:
        <br>
        <code>/scoreboard</code>
    </div>
    """

page = f"""
```

<!DOCTYPE html>

<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Select Cricket Match</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}}

.container {{
    max-width: 900px;
    margin: 40px auto;
    padding: 20px;
}}

h1 {{
    margin-bottom: 5px;
    font-size: 32px;
}}

.subtitle {{
    color: #aaa;
    margin-bottom: 30px;
}}

.match {{
    background: #1c1c1c;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 22px;
    margin-bottom: 15px;
}}

.status {{
    color: #00e676;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 10px;
}}

.match-name {{
    font-size: 20px;
    font-weight: bold;
    line-height: 1.5;
    margin-bottom: 18px;
}}

button {{
    background: #00c853;
    color: white;
    border: 0;
    padding: 13px 22px;
    border-radius: 7px;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
}}

button:hover {{
    background: #00e676;
}}

.selected {{
    background: #12351f;
    border: 1px solid #00c853;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 25px;
    line-height: 1.6;
}}

code {{
    background: #000;
    padding: 5px 8px;
    border-radius: 5px;
}}

.empty {{
    background: #1c1c1c;
    padding: 30px;
    border-radius: 12px;
    color: #aaa;
    text-align: center;
}}

.refresh {{
    margin-bottom: 25px;
    background: #333;
}}

</style>

</head>

<body>

<div class="container">

<h1>🏏 CRICKET LIVE SCORE</h1>

<div class="subtitle">
Select the match you want to display in OBS.
</div>

{selected}

<button class="refresh" onclick="location.reload()">
↻ REFRESH MATCHES
</button>

{match_html}

</div>

</body>
</html>
"""

```
return Response(page, mimetype="text/html")
```

@app.route("/select-match", methods=["POST"])
def choose_match():
match_id = request.form.get("match_id")

```
if not match_id:
    return "Match ID missing", 400

data = fetch_live_scores()

for match in data.get("matches", []):
    if str(match["id"]) == str(match_id):

        selected_match["id"] = match["id"]
        selected_match["name"] = match["name"]
        selected_match["details"] = match

        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta http-equiv="refresh" content="2;url=/select-match">
        <style>
        body {
            background:#101010;
            color:white;
            font-family:Arial;
            text-align:center;
            padding-top:100px;
        }
        .box {
            display:inline-block;
            background:#12351f;
            border:1px solid #00c853;
            padding:30px;
            border-radius:12px;
        }
        </style>
        </head>
        <body>
        <div class="box">
        <h2>✓ Match Selected</h2>
        <p>Opening match selector...</p>
        </div>
        </body>
        </html>
        """

return "Match not found. Refresh and try again.", 404
```

@app.route("/selected-match")
def selected():
return jsonify({
"success": True,
"selected_match": selected_match
})

@app.route("/scoreboard")
def scoreboard():

```
scoreboard_html = """
```

<!DOCTYPE html>

<html>
<head>

<meta charset="UTF-8">

<title>OBS Cricket Scoreboard</title>

<style>

html,
body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: transparent !important;
    overflow: hidden;
    font-family: Arial, Helvetica, sans-serif;
}

#scoreboard {
    position: absolute;
    left: 20px;
    bottom: 20px;

    min-width: 420px;
    max-width: 900px;

    background: rgba(0, 0, 0, 0.88);
    color: white;

    border-radius: 10px;

    padding: 14px 22px;

    box-shadow: 0 4px 18px rgba(0,0,0,0.35);

    font-weight: bold;
}

#live {
    color: #00e676;
    font-size: 13px;
    margin-bottom: 7px;
}

#score {
    font-size: 23px;
    line-height: 1.35;
}

#updated {
    color: #999;
    font-size: 11px;
    margin-top: 6px;
}

#error {
    color: #ff5252;
    font-size: 14px;
}

</style>

</head>

<body>

<div id="scoreboard">

```
<div id="live">
    ● LIVE CRICKET
</div>

<div id="score">
    Loading score...
</div>

<div id="updated"></div>
```

</div>

<script>

async function updateScore() {

    try {

        const response = await fetch(
            "/selected-match?t=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        const data = await response.json();

        const selected = data.selected_match;

        if (!selected || !selected.id) {

            document.getElementById("score").textContent =
                "No match selected";

            document.getElementById("updated").textContent =
                "Open /select-match to choose a match";

            return;
        }

        document.getElementById("score").textContent =
            selected.name;

        document.getElementById("updated").textContent =
            "Selected match";

    }

    catch (error) {

        document.getElementById("score").textContent =
            "Unable to load score";

    }

}


async function refreshLiveScore() {

    try {

        const response = await fetch(
            "/live-scores?t=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        const data = await response.json();

        const selected = await fetch(
            "/selected-match?t=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        const selectedData = await selected.json();

        const selectedMatch =
            selectedData.selected_match;

        if (!selectedMatch || !selectedMatch.id) {

            document.getElementById("score").textContent =
                "No match selected";

            return;
        }

        let found = null;

        for (const match of data.matches || []) {

            if (
                String(match.id) ===
                String(selectedMatch.id)
            ) {
                found = match;
                break;
            }

        }

        if (found) {

            document.getElementById("score").textContent =
                found.name;

            document.getElementById("updated").textContent =
                "Live • Auto refresh";

        } else {

            document.getElementById("score").textContent =
                selectedMatch.name;

            document.getElementById("updated").textContent =
                "Selected match • Waiting for update";

        }

    }

    catch (error) {

        document.getElementById("error").textContent =
            "Unable to load live score";

    }

}


updateScore();

refreshLiveScore();

setInterval(refreshLiveScore, 15000);

</script>

</body>
</html>
"""

```
return Response(
    scoreboard_html,
    mimetype="text/html"
)
```

@app.route("/debug")
def debug():

```
data = fetch_live_scores()

return jsonify({
    "success": True,
    "selected_match": selected_match,
    "live_score_data": data
})
```

@app.route("/debug-match")
def debug_match():

```
data = fetch_live_scores()

return jsonify(data)
```

if **name** == "**main**":

```
app.run(
    host="0.0.0.0",
    port=10000
)
```
