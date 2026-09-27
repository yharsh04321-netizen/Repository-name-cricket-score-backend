from flask import Flask, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import time

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cricbuzz.com/"
}


def clean_text(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def fetch_cricbuzz():
    response = requests.get(
        CRICBUZZ_URL,
        headers=HEADERS,
        timeout=20
    )
    response.raise_for_status()
    return response.text


def parse_score(value):
    match = re.match(
        r"^(\d{1,4})-(\d{1,2})(?:\s*\((\d{1,2}(?:\.\d)?)\))?$",
        value
    )

    if not match:
        return None

    return {
        "display": value,
        "runs": int(match.group(1)),
        "wickets": int(match.group(2)),
        "overs": match.group(3)
    }


def parse_live_matches(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    lines = []

    for line in soup.get_text("\n").splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    score_pattern = re.compile(
        r"\b\d{1,4}-\d{1,2}(?:\s*\(\d{1,2}(?:\.\d)?\))?"
    )

    status_patterns = [
        r"need\s+\d+\s+runs?",
        r"won\s+by\s+[^|]+",
        r"innings\s+break",
        r"stumps",
        r"match\s+abandoned",
        r"toss\s+delayed[^|]*",
        r"match\s+delayed[^|]*",
        r"live"
    ]

    matches = []
    seen = set()

    for i, line in enumerate(lines):

        if not score_pattern.search(line):
            continue

        start = max(0, i - 3)
        end = min(len(lines), i + 4)

        context = clean_text(" ".join(lines[start:end]))

        if len(context) > 1200:
            context = context[:1200]

        score_values = list(
            dict.fromkeys(score_pattern.findall(context))
        )

        parsed_scores = []

        for score in score_values:
            parsed = parse_score(score)

            if parsed:
                parsed_scores.append(parsed)

        if not parsed_scores:
            continue

        status = ""

        for pattern in status_patterns:
            found = re.search(
                pattern,
                context,
                re.IGNORECASE
            )

            if found:
                status = clean_text(found.group(0))
                break

        key = (
            context[:250].lower(),
            tuple(x["display"] for x in parsed_scores),
            status.lower()
        )

        if key in seen:
            continue

        seen.add(key)

        matches.append({
            "text": context,
            "scores": parsed_scores,
            "status": status
        })

    return matches


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "service": "Cricket Live Score Backend",
        "status": "online",
        "endpoints": [
            "/live-scores",
            "/scoreboard",
            "/debug",
            "/debug-match"
        ]
    })


@app.route("/live-scores")
def live_scores():

    try:
        html_content = fetch_cricbuzz()
        matches = parse_live_matches(html_content)

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches,
            "source": "Cricbuzz",
            "timestamp": int(time.time())
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Cricbuzz request failed",
            "details": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "count": 0,
            "matches": [],
            "error": "Parser error",
            "details": str(e)
        }), 500


@app.route("/scoreboard")
def scoreboard():

    return Response(
        """
<!DOCTYPE html>
<html>
<head>

<meta charset="UTF-8">

<title>Cricket Live Score</title>

<style>

html,
body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    font-family: Arial, sans-serif;
}

body {
    overflow: hidden;
}

.container {
    width: 100%;
    box-sizing: border-box;
    padding: 15px;
}

.card {
    max-width: 1100px;
    margin: auto;
    background: rgba(8, 12, 20, 0.96);
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 14px;
    padding: 20px;
    color: white;
    box-sizing: border-box;
}

.top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.title {
    font-size: 24px;
    font-weight: bold;
}

.live {
    background: #e53935;
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
}

.match {
    font-size: 16px;
    color: #d5d9e0;
    margin-bottom: 15px;
}

.teams {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.team {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 15px;
}

.team-name {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 8px;
}

.score {
    font-size: 32px;
    font-weight: 900;
}

.status {
    margin-top: 14px;
    font-size: 16px;
    font-weight: bold;
    color: #d5d9e0;
}

.footer {
    margin-top: 12px;
    text-align: right;
    color: #8d96a5;
    font-size: 11px;
}

.error {
    color: #ff6b6b;
}

@media (max-width: 700px) {

    .teams {
        grid-template-columns: 1fr;
    }

    .score {
        font-size: 27px;
    }

}

</style>

</head>

<body>

<div class="container">

    <div class="card">

        <div class="top">

            <div class="title">
                CRICKET LIVE SCORE
            </div>

            <div class="live">
                ● LIVE
            </div>

        </div>

        <div id="content">
            Loading...
        </div>

        <div class="footer">
            Auto refresh: 15 seconds
        </div>

    </div>

</div>

<script>

function safe(value) {

    var div = document.createElement("div");

    div.textContent = value || "";

    return div.innerHTML;

}


function render(match) {

    var scores = match.scores || [];

    var score1 = scores.length > 0
        ? scores[0].display
        : "-";

    var score2 = scores.length > 1
        ? scores[1].display
        : "-";

    var text = match.text || "";

    var status = match.status || "";

    var parts = text.split(" ");

    var team1 = "Team 1";
    var team2 = "Team 2";

    if (parts.length >= 4) {

        var scoreIndex = -1;

        for (var i = 0; i < parts.length; i++) {

            if (/^\d+-\d+/.test(parts[i])) {
                scoreIndex = i;
                break;
            }

        }

        if (scoreIndex >= 2) {
            team1 = parts[scoreIndex - 2] || "Team 1";
        }

        if (scoreIndex >= 1 && scoreIndex + 1 < parts.length) {
            team2 = parts[scoreIndex + 1] || "Team 2";
        }

    }

    return (
        '<div class="match">' +
        safe(text) +
        '</div>' +

        '<div class="teams">' +

        '<div class="team">' +
        '<div class="team-name">' +
        safe(team1) +
        '</div>' +
        '<div class="score">' +
        safe(score1) +
        '</div>' +
        '</div>' +

        '<div class="team">' +
        '<div class="team-name">' +
        safe(team2) +
        '</div>' +
        '<div class="score">' +
        safe(score2) +
        '</div>' +
        '</div>' +

        '</div>' +

        (
            status
            ? '<div class="status">' +
              safe(status) +
              '</div>'
            : ''
        )
    );

}


async function updateScore() {

    var content = document.getElementById("content");

    try {

        var response = await fetch(
            "/live-scores?t=" + Date.now()
        );

        if (!response.ok) {
            throw new Error(
                "HTTP " + response.status
            );
        }

        var data = await response.json();

        if (!data.success) {
            throw new Error(
                data.error || "Score request failed"
            );
        }

        if (!data.matches || data.matches.length === 0) {

            content.innerHTML =
                '<div class="status">' +
                'No live matches found.' +
                '</div>';

            return;
        }

        content.innerHTML =
            render(data.matches[0]);

    } catch (error) {

        content.innerHTML =
            '<div class="error">' +
            'Unable to load live score.' +
            '</div>';

        console.log(error);

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
        """,
        mimetype="text/html"
    )


@app.route("/debug")
def debug():

    try:

        html_content = fetch_cricbuzz()

        soup = BeautifulSoup(
            html_content,
            "html.parser"
        )

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        page_text = clean_text(
            soup.get_text(" ", strip=True)
        )

        scores = re.findall(
            r"\b\d{1,4}-\d{1,2}(?:\s*\(\d{1,2}(?:\.\d)?\))?",
            page_text
        )

        return jsonify({
            "success": True,
            "status_code": 200,
            "page_length": len(html_content),
            "india_found": "India" in html_content,
            "west_indies_found": "West Indies" in html_content,
            "score_samples": list(
                dict.fromkeys(scores)
            )[:30],
            "page_preview": page_text[:3000]
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "error": "Cricbuzz request failed",
            "details": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Debug error",
            "details": str(e)
        }), 500


@app.route("/debug-match")
def debug_match():

    try:

        html_content = fetch_cricbuzz()

        search_terms = [
            "West Indies tour of India",
            "West Indies",
            "India need",
            "WI",
            "IND"
        ]

        position = -1
        matched_term = None

        for term in search_terms:

            position = html_content.find(term)

            if position != -1:
                matched_term = term
                break

        if position == -1:

            return jsonify({
                "success": False,
                "message": "Match text not found",
                "page_length": len(html_content)
            })

        start = max(
            0,
            position - 5000
        )

        end = min(
            len(html_content),
            position + 15000
        )

        return jsonify({
            "success": True,
            "matched_term": matched_term,
            "position": position,
            "html_length": len(html_content),
            "section": html_content[start:end]
        })

    except requests.RequestException as e:

        return jsonify({
            "success": False,
            "error": "Cricbuzz request failed",
            "details": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Debug error",
            "details": str(e)
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
