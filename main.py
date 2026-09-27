from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_live_scores():
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

        for item in soup.select(".cb-mtch-lst"):
            text = " ".join(item.stripped_strings)

            if text:
                matches.append(text)

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


@app.route("/scoreboard")
def scoreboard():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Cricket Scoreboard</title>

<style>
html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    overflow: hidden;
    font-family: Arial, sans-serif;
}

.scoreboard {
    margin: 20px;
    padding: 15px 25px;
    background: rgba(10, 10, 10, 0.92);
    color: white;
    border-radius: 12px;
    font-size: 24px;
    font-weight: bold;
}

.live {
    color: #ff3333;
    font-size: 14px;
    margin-bottom: 8px;
}
</style>
</head>

<body>

<div class="scoreboard">
    <div class="live">● LIVE SCORE</div>
    <div id="score">Loading...</div>
</div>

<script>
async function updateScore() {
    try {
        const response = await fetch(
            "/live-scores?t=" + Date.now(),
            {cache: "no-store"}
        );

        const data = await response.json();

        if (data.matches && data.matches.length > 0) {
            document.getElementById("score").textContent =
                data.matches[0];
        } else {
            document.getElementById("score").textContent =
                "No live match currently available";
        }

    } catch (error) {
        document.getElementById("score").textContent =
            "Unable to load live score";
    }
}

updateScore();
setInterval(updateScore, 15000);
</script>

</body>
</html>
"""

    return Response(
        html,
        mimetype="text/html"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
