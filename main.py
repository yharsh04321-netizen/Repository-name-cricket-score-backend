from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import time

app = Flask(**name**)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
TIMEOUT = 15

def parse_score(text):
if not text:
return {
"display": "",
"runs": None,
"wickets": None,
"overs": None
}

```
text = text.strip()

match = re.search(
    r"(\d+)\s*-\s*(\d+)(?:\s*\(([\d.]+)\))?",
    text
)

if not match:
    return {
        "display": text,
        "runs": None,
        "wickets": None,
        "overs": None
    }

return {
    "display": text,
    "runs": int(match.group(1)),
    "wickets": int(match.group(2)),
    "overs": match.group(3)
}
```

def fetch_cricbuzz():
headers = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 "
"(KHTML, like Gecko) "
"Chrome/140.0.0.0 Safari/537.36"
)
}

```
response = requests.get(
    CRICBUZZ_URL,
    headers=headers,
    timeout=TIMEOUT
)

response.raise_for_status()

return BeautifulSoup(
    response.text,
    "html.parser"
)
```

def get_live_scores():
soup = fetch_cricbuzz()

```
matches = []

cards = soup.select("div.cb-mtch-lst")

for card in cards:

    text = card.get_text(
        " ",
        strip=True
    )

    if not text:
        continue

    score_texts = re.findall(
        r"\d+\s*-\s*\d+(?:\s*\([\d.]+\))?",
        text
    )

    scores = [
        parse_score(score)
        for score in score_texts[:2]
    ]

    if not scores:
        continue

    status = ""

    status_element = card.select_one(
        ".cb-text-live, "
        ".cb-text-complete, "
        ".cb-text-inprogress, "
        ".cb-text-stump"
    )

    if status_element:
        status = status_element.get_text(
            " ",
            strip=True
        )

    matches.append({
        "scores": scores,
        "status": status,
        "text": re.sub(
            r"\s+",
            " ",
            text
        ).strip()
    })

return matches
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

```
try:

    matches = get_live_scores()

    return jsonify({
        "success": True,
        "source": "Cricbuzz",
        "count": len(matches),
        "matches": matches,
        "timestamp": int(time.time())
    })

except Exception as e:

    return jsonify({
        "success": False,
        "source": "Cricbuzz",
        "count": 0,
        "matches": [],
        "error": str(e),
        "timestamp": int(time.time())
    }), 500
```

@app.route("/debug")
def debug():

```
try:

    response = requests.get(
        CRICBUZZ_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=TIMEOUT
    )

    return jsonify({
        "success": True,
        "status_code": response.status_code,
        "page_length": len(response.text)
    })

except Exception as e:

    return jsonify({
        "success": False,
        "error": str(e)
    }), 500
```

@app.route("/debug-match")
def debug_match():

```
try:

    matches = get_live_scores()

    return jsonify({
        "success": True,
        "count": len(matches),
        "matches": matches[:5]
    })

except Exception as e:

    return jsonify({
        "success": False,
        "error": str(e)
    }), 500
```

@app.route("/scoreboard")
def scoreboard():

```
html = """<!DOCTYPE html>
```

<html>
<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width,initial-scale=1.0"

>

<title>Cricket Live Score</title>

<style>

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;

    overflow: hidden;

    background: transparent !important;
}

body {

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    color: white;

    background: transparent !important;

    display: flex;

    align-items: flex-end;

    justify-content: center;

    padding: 30px;
}

#scoreboard {

    width: 100%;

    max-width: 1700px;

    display: none;

    background:
        linear-gradient(
            135deg,
            rgba(10,15,25,0.97),
            rgba(20,25,35,0.94)
        );

    border: 2px solid
        rgba(255,255,255,0.18);

    border-radius: 18px;

    box-shadow:
        0 12px 40px
        rgba(0,0,0,0.55);

    overflow: hidden;
}

.header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    padding: 12px 24px;

    background:
        rgba(255,255,255,0.08);

    font-size: 18px;

    font-weight: 800;
}

.live {

    display: flex;

    align-items: center;

    gap: 8px;

    color: #7CFF8A;
}

.dot {

    width: 10px;

    height: 10px;

    border-radius: 50%;

    background: #7CFF8A;

    box-shadow:
        0 0 12px #7CFF8A;
}

.content {

    padding: 18px 25px 22px;
}

.title {

    color:
        rgba(255,255,255,0.68);

    font-size: 19px;

    margin-bottom: 15px;

    white-space: nowrap;

    overflow: hidden;

    text-overflow: ellipsis;
}

.teams {

    display: grid;

    grid-template-columns:
        1fr 70px 1fr;

    align-items: center;

    gap: 20px;
}

.team {

    display: flex;

    flex-direction: column;

    gap: 5px;
}

.team.right {

    text-align: right;

    align-items: flex-end;
}

.name {

    font-size: 28px;

    font-weight: 800;
}

.score {

    font-size: 48px;

    line-height: 1;

    font-weight: 900;
}

.overs {

    color:
        rgba(255,255,255,0.60);

    font-size: 17px;
}

.vs {

    text-align: center;

    color:
        rgba(255,255,255,0.40);

    font-weight: 800;

    font-size: 18px;
}

.status {

    margin-top: 18px;

    padding: 10px 15px;

    border-radius: 10px;

    background:
        rgba(255,255,255,0.08);

    text-align: center;

    font-size: 20px;

    font-weight: 800;
}

#error {

    display: none;

    width: 100%;

    max-width: 1700px;

    padding: 18px;

    border-radius: 14px;

    background:
        rgba(160,25,25,0.95);

    text-align: center;

    font-size: 20px;
}

</style>

</head>

<body>

<div id="scoreboard">

```
<div class="header">

    <div>
        CRICKET LIVE
    </div>

    <div class="live">

        <span class="dot"></span>

        LIVE

    </div>

</div>

<div class="content">

    <div
        id="title"
        class="title"
    >
        Loading live match...
    </div>

    <div class="teams">

        <div class="team">

            <div
                id="team1"
                class="name"
            >
                Team 1
            </div>

            <div
                id="score1"
                class="score"
            >
                --
            </div>

            <div
                id="overs1"
                class="overs"
            >
            </div>

        </div>

        <div class="vs">
            VS
        </div>

        <div class="team right">

            <div
                id="team2"
                class="name"
            >
                Team 2
            </div>

            <div
                id="score2"
                class="score"
            >
                --
            </div>

            <div
                id="overs2"
                class="overs"
            >
            </div>

        </div>

    </div>

    <div
        id="status"
        class="status"
    >
        Loading...
    </div>

</div>
```

</div>

<div id="error">
    Unable to load live score
</div>

<script>

function getTeams(text) {

    if (!text) {
        return ["Team 1", "Team 2"];
    }

    const scorePattern =
        /\d+\s*-\s*\d+(?:\s*\([\d.]+\))?/g;

    const parts =
        text.split(scorePattern);

    const names = [];

    for (let i = 0; i < parts.length; i++) {

        let value = parts[i]
            .replace(/Live Score/gi, "")
            .replace(/need\s+\d+\s+runs?/gi, "")
            .replace(/won\s+by.*$/i, "")
            .replace(/\s+/g, " ")
            .trim();

        if (value.length > 2) {
            names.push(value);
        }
    }

    if (names.length >= 2) {

        return [
            names[names.length - 2],
            names[names.length - 1]
        ];
    }

    return ["Team 1", "Team 2"];
}


function showScores(data) {

    const board =
        document.getElementById("scoreboard");

    const error =
        document.getElementById("error");

    if (
        !data ||
        !data.success ||
        !data.matches ||
        data.matches.length === 0
    ) {

        board.style.display = "none";

        error.style.display = "block";

        return;
    }

    const match =
        data.matches[0];

    const scores =
        match.scores || [];

    const first =
        scores[0] || {};

    const second =
        scores[1] || {};

    const teams =
        getTeams(match.text || "");

    document.getElementById("team1")
        .textContent = teams[0];

    document.getElementById("team2")
        .textContent = teams[1];

    document.getElementById("score1")
        .textContent =
            first.display || "--";

    document.getElementById("score2")
        .textContent =
            second.display || "--";

    document.getElementById("overs1")
        .textContent =
            first.overs
                ? "Overs " + first.overs
                : "";

    document.getElementById("overs2")
        .textContent =
            second.overs
                ? "Overs " + second.overs
                : "";

    document.getElementById("title")
        .textContent =
            match.text ||
            "Live Cricket Match";

    document.getElementById("status")
        .textContent =
            match.status ||
            "LIVE";

    board.style.display = "block";

    error.style.display = "none";
}


async function loadScores() {

    try {

        const response =
            await fetch(
                "/live-scores?t=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                "HTTP " +
                response.status
            );
        }

        const data =
            await response.json();

        showScores(data);

    } catch (error) {

        console.error(
            "Scoreboard error:",
            error
        );

        document.getElementById(
            "scoreboard"
        ).style.display = "none";

        document.getElementById(
            "error"
        ).style.display = "block";
    }
}


loadScores();

setInterval(
    loadScores,
    15000
);

</script>

</body>
</html>"""

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
