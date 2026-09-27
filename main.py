from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/131.0 Safari/537.36"
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

    selectors = [
        ".cb-mtch-lst",
        ".cb-mtch-lst-v1"
    ]

    for selector in selectors:
        for item in soup.select(selector):
            text = " ".join(item.stripped_strings)

            if text and text not in matches:
                matches.append(text)

        if matches:
            break

    return {
        "success": True,
        "matches": matches,
        "count": len(matches),
        "source": "Cricbuzz"
    }

except requests.RequestException as error:
    return {
        "success": False,
        "matches": [],
        "count": 0,
        "error": "Network error: " + str(error)
    }

except Exception as error:
    return {
        "success": False,
        "matches": [],
        "count": 0,
        "error": "Parsing error: " + str(error)
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
return jsonify(fetch_live_scores())

@app.route("/debug")
def debug():
return jsonify(fetch_live_scores())

@app.route("/debug-match")
def debug_match():
data = fetch_live_scores()

```
if not data["matches"]:
    return jsonify({
        "success": False,
        "message": "No live match found",
        "data": data
    })

match_text = data["matches"][0]

scores = re.findall(
    r"\b\d{1,4}/\d{1,3}(?:\s*\(\d+(?:\.\d+)?\))?",
    match_text
)

return jsonify({
    "success": True,
    "raw": match_text,
    "scores": scores
})
```

@app.route("/scoreboard")
def scoreboard():

```
html = """
```

<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"

>

<title>Cricket Live Score</title>

<style>

html,
body {
    margin: 0;
    padding: 0;

    width: 100%;
    height: 100%;

    background: transparent;

    overflow: hidden;

    font-family:
        Arial,
        Helvetica,
        sans-serif;
}

body {
    display: flex;

    justify-content: center;

    align-items: flex-start;
}

.scoreboard {

    width: 96%;

    max-width: 1100px;

    margin-top: 20px;

    color: white;

    background: rgba(8, 12, 20, 0.94);

    border: 2px solid rgba(255, 255, 255, 0.18);

    border-radius: 14px;

    overflow: hidden;

    box-sizing: border-box;

    box-shadow:
        0 8px 30px rgba(0, 0, 0, 0.35);
}

.header {

    display: flex;

    justify-content: space-between;

    align-items: center;

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

    box-shadow:
        0 0 10px #ff3b30;
}

.score {

    padding: 22px;

    text-align: center;

    font-size: 24px;

    font-weight: bold;

    line-height: 1.4;

    word-wrap: break-word;
}

.loading {

    color: rgba(255, 255, 255, 0.65);
}

.error {

    color: #ff8a80;

    font-size: 17px;
}

</style>

</head>

<body>

<div class="scoreboard">

```
<div class="header">

    <div>
        CRICKET LIVE SCORE
    </div>

    <div class="live">

        <span class="live-dot"></span>

        LIVE

    </div>

</div>

<div
    id="score"
    class="score loading"
>
    Loading live score...
</div>
```

</div>

<script>

async function updateScore() {

    const scoreElement =
        document.getElementById("score");

    try {

        const response = await fetch(
            "/live-scores?ts=" + Date.now(),
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                "HTTP " + response.status
            );
        }

        const data =
            await response.json();

        if (!data.success) {

            scoreElement.className =
                "score error";

            scoreElement.textContent =
                data.error ||
                "Unable to load live score";

            return;
        }

        if (
            !data.matches ||
            data.matches.length === 0
        ) {

            scoreElement.className =
                "score loading";

            scoreElement.textContent =
                "No live match currently available";

            return;
        }

        scoreElement.className =
            "score";

        scoreElement.textContent =
            data.matches[0];

    } catch (error) {

        scoreElement.className =
            "score error";

        scoreElement.textContent =
            "Live score temporarily unavailable";

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

if **name** == "**main**":

```
app.run(
    host="0.0.0.0",
    port=10000,
    debug=False
)
```
