from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import json
import time

app = Flask(**name**)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/131.0.0.0 Safari/537.36"
)
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

    for item in soup.select(".cb-mtch-lst"):
        text = " ".join(item.stripped_strings)

        if not text:
            continue

        matches.append({
            "text": text
        })

    if not matches:
        for item in soup.select(".cb-mtch-lst-v1"):
            text = " ".join(item.stripped_strings)

            if text:
                matches.append({
                    "text": text
                })

    return {
        "success": True,
        "matches": matches,
        "count": len(matches),
        "source": "Cricbuzz"
    }

except requests.RequestException as exc:
    return {
        "success": False,
        "matches": [],
        "count": 0,
        "error": f"Network error: {str(exc)}",
        "source": "Cricbuzz"
    }

except Exception as exc:
    return {
        "success": False,
        "matches": [],
        "count": 0,
        "error": str(exc),
        "source": "Cricbuzz"
    }
```

def parse_score(text):
if not text:
return {
"team1": "",
"team2": "",
"score1": "",
"score2": "",
"status": ""
}

```
score_patterns = re.findall(
    r"\b\d{1,4}/\d{1,3}(?:\s*\(\d+(?:\.\d+)?\))?",
    text
)

status = ""

lower = text.lower()

if "won" in lower:
    status = text
elif "live" in lower:
    status = "LIVE"
elif "stumps" in lower:
    status = "STUMPS"
elif "innings break" in lower:
    status = "INNINGS BREAK"
elif "break" in lower:
    status = "BREAK"
elif "scheduled" in lower:
    status = "SCHEDULED"

return {
    "team1": "",
    "team2": "",
    "score1": score_patterns[0] if len(score_patterns) > 0 else "",
    "score2": score_patterns[1] if len(score_patterns) > 1 else "",
    "status": status
}
```

@app.route("/")
def home():
return jsonify({
"service": "Cricket Live Score Backend",
"status": "online",
"success": True,
"endpoints": [
"/live-scores",
"/scoreboard",
"/debug",
"/debug-match"
]
})

@app.route("/live-scores")
def live_scores():
data = fetch_live_scores()
return jsonify(data)

@app.route("/debug")
def debug():
data = fetch_live_scores()

```
return jsonify({
    "success": data.get("success", False),
    "count": data.get("count", 0),
    "error": data.get("error"),
    "matches": data.get("matches", [])
})
```

@app.route("/debug-match")
def debug_match():
data = fetch_live_scores()

```
if not data.get("matches"):
    return jsonify({
        "success": False,
        "message": "No live match found",
        "data": data
    })

first_match = data["matches"][0]

return jsonify({
    "success": True,
    "raw": first_match,
    "parsed": parse_score(first_match.get("text", ""))
})
```

@app.route("/scoreboard")
def scoreboard():
html = """

<!DOCTYPE html>

<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Cricket Scoreboard</title>

<style>
html,
body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    overflow: hidden;
    font-family: Arial, Helvetica, sans-serif;
}

body {
    display: flex;
    align-items: center;
    justify-content: center;
}

.scoreboard {
    width: 96%;
    max-width: 1100px;
    min-height: 110px;
    box-sizing: border-box;

    background: rgba(10, 15, 25, 0.92);
    border: 2px solid rgba(255, 255, 255, 0.18);
    border-radius: 14px;

    color: white;

    box-shadow:
        0 8px 30px rgba(0, 0, 0, 0.35);

    overflow: hidden;
}

.header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 10px 18px;

    background: rgba(0, 0, 0, 0.35);

    font-size: 14px;
    font-weight: bold;
}

.live {
    display: flex;
    align-items: center;
    gap: 7px;

    color: #ff5252;
}

.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff3b30;

    box-shadow: 0 0 10px #ff3b30;
}

.content {
    padding: 18px 22px;
}

.match-text {
    font-size: 24px;
    line-height: 1.35;
    font-weight: 700;
    text-align: center;
}

.empty {
    color: rgba(255, 255, 255, 0.65);
    text-align: center;
    font-size: 20px;
}

.error {
    color: #ff8a80;
    text-align: center;
    font-size: 16px;
}
</style>

</head>

<body>

<div class="scoreboard">

```
<div class="header">
    <div>CRICKET LIVE SCORE</div>

    <div class="live">
        <span class="live-dot"></span>
        LIVE
    </div>
</div>

<div class="content">
    <div id="score" class="empty">
        Loading live score...
    </div>
</div>
```

</div>

<script>
async function loadScore() {
    const scoreElement = document.getElementById("score");

    try {
        const response = await fetch("/live-scores", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("HTTP " + response.status);
        }

        const data = await response.json();

        if (!data.success) {
            scoreElement.className = "error";
            scoreElement.textContent =
                data.error || "Unable to load live score";
            return;
        }

        if (!data.matches || data.matches.length === 0) {
            scoreElement.className = "empty";
            scoreElement.textContent =
                "No live match currently available";
            return;
        }

        scoreElement.className = "match-text";

        const match = data.matches[0];

        scoreElement.textContent =
            match.text || "Live score unavailable";

    } catch (error) {
        scoreElement.className = "error";

        scoreElement.textContent =
            "Unable to fetch live score";
    }
}

loadScore();

setInterval(loadScore, 15000);
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

if **name** == "**main**":
app.run(
host="0.0.0.0",
port=10000,
debug=False
)
