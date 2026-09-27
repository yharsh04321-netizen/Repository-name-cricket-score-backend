from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup

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

        matches.append({
            "id": str(index),
            "name": text
        })

    return matches

except Exception:
    return []
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
matches = fetch_matches()

```
return jsonify({
    "success": True,
    "count": len(matches),
    "matches": matches
})
```

@app.route("/select-match", methods=["GET", "POST"])
def select_match():

```
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

        <div class="live">
            ● LIVE / MATCH
        </div>

        <div class="name">
            {match["name"]}
        </div>

        <form method="POST">

            <input
                type="hidden"
                name="match_id"
                value="{match["id"]}"
            >

            <button>
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

selected = ""

if selected_match:

    selected = f"""
    <div class="selected">

        ✓ SELECTED MATCH

        <br><br>

        <strong>
            {selected_match["name"]}
        </strong>

        <br><br>

        Use this URL in OBS:

        <br>

        <code>
            /scoreboard
        </code>

    </div>
    """

html = f"""
```

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>Select Match</title>

<style>

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

.selected {{
    background: #12351f;
    border: 1px solid #00c853;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
}}

.empty {{
    background: #1d1d1d;
    padding: 30px;
    text-align: center;
    color: #aaa;
    border-radius: 10px;
}}

code {{
    background: #000;
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

{selected}

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
    html,
    mimetype="text/html"
)
```

@app.route("/scoreboard")
def scoreboard():

```
html = """
```

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>OBS Scoreboard</title>

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
```

</div>

<script>

async function updateScore() {

    try {

        const response = await fetch(
            "/live-scores?t=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        const data =
            await response.json();

        if (
            data.matches &&
            data.matches.length > 0
        ) {

            document.getElementById(
                "score"
            ).textContent =
                data.matches[0].name;

        } else {

            document.getElementById(
                "score"
            ).textContent =
                "No live match";

        }

    } catch (error) {

        document.getElementById(
            "score"
        ).textContent =
            "Score unavailable";

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
    html,
    mimetype="text/html"
)
```

@app.route("/selected-match")
def selected():

```
return jsonify({
    "success": True,
    "match": selected_match
})
```

if **name** == "**main**":

```
app.run(
    host="0.0.0.0",
    port=10000
)
```
