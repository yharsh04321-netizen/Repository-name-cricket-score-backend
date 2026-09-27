from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(**name**)

CRICBUZZ_URL = "https://www.cricbuzz.com/live-cricket-scores"

def get_live_scores():
try:
response = requests.get(
CRICBUZZ_URL,
headers={"User-Agent": "Mozilla/5.0"},
timeout=15
)

```
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    matches = []

    for item in soup.select(".cb-col.cb-col-100.cb-scrd-itms"):
        text = " ".join(item.stripped_strings)

        if not text:
            continue

        scores = re.findall(
            r"\b\d+(?:-\d+)?\s*\(\d+(?:\.\d+)?\)",
            text
        )

        if scores:
            matches.append({
                "text": text,
                "scores": scores
            })

    return matches

except Exception as e:
    print("Score fetch error:", e)
    return []
```

@app.route("/")
def home():
return jsonify({
"success": True,
"status": "online",
"service": "Cricket Live Score Backend",
"endpoints": [
"/live-scores",
"/scoreboard",
"/debug",
"/debug-match"
]
})

@app.route("/live-scores")
def live_scores():
matches = get_live_scores()

```
return jsonify({
    "success": True,
    "count": len(matches),
    "matches": matches
})
```

@app.route("/debug")
def debug():
matches = get_live_scores()

```
return jsonify({
    "success": True,
    "count": len(matches),
    "matches": matches
})
```

@app.route("/debug-match")
def debug_match():
matches = get_live_scores()

```
return jsonify({
    "success": True,
    "matches": matches[:5]
})
```

@app.route("/scoreboard")
def scoreboard():

```
page = """
```

<!DOCTYPE html>

<html>
<head>
<meta charset="UTF-8">

<title>Cricket OBS Scoreboard</title>

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

body {
    background: rgba(0,0,0,0) !important;
}

#scoreboard {
    position: absolute;
    left: 30px;
    right: 30px;
    bottom: 30px;

    background: rgba(10,10,10,0.88);

    border: 2px solid rgba(255,255,255,0.15);
    border-radius: 14px;

    box-shadow: 0 8px 30px rgba(0,0,0,0.45);

    color: white;

    overflow: hidden;

    display: none;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    padding: 10px 18px;

    background: linear-gradient(
        90deg,
        rgba(0,120,255,0.95),
        rgba(0,180,120,0.95)
    );

    font-weight: bold;
    font-size: 18px;
}

.live {
    display: flex;
    align-items: center;
    gap: 7px;
}

.live-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #ff3030;
    box-shadow: 0 0 10px #ff3030;
}

.match {
    padding: 15px 20px;
}

.teams {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
}

.team {
    flex: 1;
    font-size: 24px;
    font-weight: bold;
}

.team.right {
    text-align: right;
}

.score {
    font-size: 34px;
    font-weight: 900;
    white-space: nowrap;
}

.status {
    margin-top: 8px;
    font-size: 17px;
    font-weight: bold;
    color: #7dff9c;
}

.details {
    margin-top: 6px;
    color: rgba(255,255,255,0.7);
    font-size: 14px;
}

</style>

</head>

<body>

<div id="scoreboard">

```
<div class="header">

    <div>CRICKET LIVE</div>

    <div class="live">
        <span class="live-dot"></span>
        LIVE
    </div>

</div>

<div id="content"></div>
```

</div>

<script>

function escapeHTML(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function showScoreboard(matches) {

    const board = document.getElementById("scoreboard");
    const content = document.getElementById("content");

    if (!matches || matches.length === 0) {
        board.style.display = "none";
        return;
    }

    const match = matches[0];

    const text = match.text || "";
    const scores = match.scores || [];

    const score1 = scores[0] || "";
    const score2 = scores[1] || "";

    let team1 = "TEAM 1";
    let team2 = "TEAM 2";

    const parts = text.split(" ");
    const teamNames = [];

    for (let i = 0; i < parts.length; i++) {

        if (
            parts[i].length >= 2 &&
            parts[i].length <= 5 &&
            /^[A-Z]+$/.test(parts[i])
        ) {

            if (
                parts[i] !== "LIVE" &&
                parts[i] !== "SCORE" &&
                parts[i] !== "ODI" &&
                parts[i] !== "TEST" &&
                parts[i] !== "T20"
            ) {
                teamNames.push(parts[i]);
            }
        }
    }

    if (teamNames.length >= 2) {
        team1 = teamNames[0];
        team2 = teamNames[1];
    }

    content.innerHTML = `
        <div class="match">

            <div class="teams">

                <div class="team">
                    ${escapeHTML(team1)}
                </div>

                <div class="score">
                    ${escapeHTML(score1)}
                </div>

                <div class="team right">
                    ${escapeHTML(team2)}
                </div>

            </div>

            ${
                match.status
                ? `<div class="status">${escapeHTML(match.status)}</div>`
                : ""
            }

            <div class="details">
                ${escapeHTML(text)}
            </div>

        </div>
    `;

    board.style.display = "block";
}


async function updateScoreboard() {

    try {

        const response = await fetch(
            "/live-scores?t=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error("API request failed");
        }

        const data = await response.json();

        showScoreboard(data.matches || []);

    } catch (error) {

        console.log("Score update failed:", error);

    }
}


updateScoreboard();

setInterval(updateScoreboard, 15000);

</script>

</body>
</html>
"""

```
return Response(page, mimetype="text/html")
```

if **name** == "**main**":
port = int(os.environ.get("PORT", 10000))

```
app.run(
    host="0.0.0.0",
    port=port
)
```
