from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
import html
import re
app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
"User-Agent": "Mozilla/5.0"
}

selected_match = {
"id": None,
"name": None,
"url": None
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

        link = item.select_one(
            "a[href*='/live-cricket-scores/']"
        )

        url = ""

        if link:
            url = link.get("href", "")

        if url.startswith("/"):
            url = "https://www.cricbuzz.com" + url

        match_id = str(index)

        found_id = re.search(
            r"(\d{5,})",
            url
        )

        if found_id:
            match_id = found_id.group(1)

        matches.append({
            "id": match_id,
            "name": text,
            "url": url
        })

    return {
        "success": True,
        "count": len(matches),
        "matches": matches
    }

except Exception as error:
    return {
        "success": False,
        "count": 0,
        "matches": [],
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
return jsonify(
fetch_live_scores()
)

@app.route("/select-match", methods=["GET"])
def select_match_page():
data = fetch_live_scores()

```
matches = data.get(
    "matches",
    []
)

cards = ""

for match in matches:
    match_id = html.escape(
        str(match["id"])
    )

    match_name = html.escape(
        match["name"]
    )

    cards += f"""
    <div class="match">

        <div class="live">
            ● LIVE / MATCH
        </div>

        <div class="name">
            {match_name}
        </div>

        <form method="POST"
              action="/select-match">

            <input
                type="hidden"
                name="match_id"
                value="{match_id}"
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
        No matches found.
        <br><br>
        Click REFRESH MATCHES.
    </div>
    """

selected_html = ""

if selected_match["id"]:
    selected_html = f"""
    <div class="selected">

        <div>
            ✓ SELECTED MATCH
        </div>

        <strong>
            {html.escape(
                str(selected_match["name"])
            )}
        </strong>

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

<title>Select Cricket Match</title>

<style>

body {{
    margin: 0;
    background: #101010;
    color: white;
    font-family: Arial, sans-serif;
}}

.container {{
    width: 90%;
    max-width: 900px;
    margin: 40px auto;
}}

h1 {{
    font-size: 32px;
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
    font-size: 20px;
    font-weight: bold;
    margin-bottom: 18px;
}}

button {{
    background: #00c853;
    color: white;
    border: none;
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

.selected {{
    background: #12351f;
    border: 1px solid #00c853;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    line-height: 1.6;
}}

.empty {{
    background: #1d1d1d;
    padding: 30px;
    text-align: center;
    color: #aaa;
    border-radius: 10px;
}}

code {{
    background: black;
    padding: 5px 8px;
    border-radius: 5px;
}}

</style>

</head>

<body>

<div class="container">

<h1>
🏏 CRICKET LIVE SCORE
</h1>

<div class="subtitle">
Select today's match for your OBS scoreboard.
</div>

{selected_html}

<button
 class="refresh"
 onclick="location.reload()">
↻ REFRESH MATCHES </button>

{cards}

</div>

</body>

</html>
"""

```
return Response(
    page,
    mimetype="text/html"
)
```

@app.route("/select-match", methods=["POST"])
def select_match():
match_id = request.form.get(
"match_id"
)

```
if not match_id:
    return "Match ID missing", 400

data = fetch_live_scores()

for match in data.get(
    "matches",
    []
):

    if str(match["id"]) == str(match_id):

        selected_match["id"] = match["id"]

        selected_match["name"] = match["name"]

        selected_match["url"] = match["url"]

        return """
        <html>
        <head>
        <meta http-equiv="refresh"
              content="1;url=/select-match">
        </head>

        <body style="
            background:#101010;
            color:white;
            font-family:Arial;
            text-align:center;
            padding-top:100px;
        ">

        <h1>✓ Match Selected</h1>

        <p>Returning to match selector...</p>

        </body>
        </html>
        """

return "Match not found. Refresh the selector.", 404
```

@app.route("/selected-match")
def get_selected_match():
return jsonify({
"success": True,
"selected_match": selected_match
})

@app.route("/scoreboard")
def scoreboard():

```
page = """
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
    font-family: Arial, sans-serif;
}

.scoreboard {
    position: absolute;
    left: 20px;
    bottom: 20px;

    min-width: 420px;

    padding: 14px 22px;

    background: rgba(0, 0, 0, 0.88);

    color: white;

    border-radius: 10px;

    font-weight: bold;
}

.live {
    color: #00e676;
    font-size: 13px;
    margin-bottom: 7px;
}

.score {
    font-size: 23px;
    line-height: 1.35;
}

.updated {
    color: #999;
    font-size: 11px;
    margin-top: 6px;
}

</style>

</head>

<body>

<div class="scoreboard">

```
<div class="live">
    ● LIVE CRICKET
</div>

<div
    id="score"
    class="score">
    Loading...
</div>

<div
    id="updated"
    class="updated">
</div>
```

</div>

<script>

async function updateScore() {

    try {

        const response = await fetch(
            "/selected-match?t=" +
            Date.now(),
            {
                cache: "no-store"
            }
        );

        const data =
            await response.json();

        const match =
            data.selected_match;

        if (!match || !match.id) {

            document.getElementById(
                "score"
            ).textContent =
                "No match selected";

            document.getElementById(
                "updated"
            ).textContent =
                "Open /select-match";

            return;
        }

        document.getElementById(
            "score"
        ).textContent =
            match.name;

        document.getElementById(
            "updated"
        ).textContent =
            "Selected match • Auto refresh";

    } catch (error) {

        document.getElementById(
            "score"
        ).textContent =
            "Unable to load score";

    }

}

updateScore();

setInterval(
    updateScore,
    15000
);

</script>

</body>

</html>
"""

```
return Response(
    page,
    mimetype="text/html"
)
```

@app.route("/debug")
def debug():

```
return jsonify({
    "selected_match": selected_match,
    "live_scores": fetch_live_scores()
})
```

@app.route("/debug-match")
def debug_match():

```
return jsonify(
    fetch_live_scores()
)
```

if **name** == "**main**":

```
app.run(
    host="0.0.0.0",
    port=10000
)
```
