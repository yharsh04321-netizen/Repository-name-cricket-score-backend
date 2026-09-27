```python
from flask import Flask, jsonify, request
import os
import requests

app = Flask(__name__)

# Render Environment Variable
API_KEY = os.environ.get("CRICKET_API_KEY")

CURRENT_MATCHES_URL = "https://api.cricapi.com/v1/currentMatches"


@app.route("/")
def home():
    return jsonify({
        "message": "Cricket Score Backend is running",
        "status": "online",
        "provider": "CricketData"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_configured": bool(API_KEY)
    })


@app.route("/live")
def live_scores():

    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "CRICKET_API_KEY is not configured in Render",
            "matches": []
        }), 500

    try:
        response = requests.get(
            CURRENT_MATCHES_URL,
            params={
                "apikey": API_KEY,
                "offset": 0
            },
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "success":
            return jsonify({
                "success": False,
                "error": data.get(
                    "info",
                    "CricketData API returned an error"
                ),
                "matches": []
            }), 502

        api_matches = data.get("data", [])

        matches = []

        for match in api_matches:

            matches.append({
                "id": match.get("id"),
                "name": match.get("name"),
                "matchType": match.get("matchType"),
                "status": match.get("status"),
                "venue": match.get("venue"),
                "date": match.get("date"),
                "dateTimeGMT": match.get("dateTimeGMT"),

                "teams": match.get(
                    "teams",
                    []
                ),

                "teamInfo": match.get(
                    "teamInfo",
                    []
                ),

                "score": match.get(
                    "score",
                    []
                ),

                "series_id": match.get(
                    "series_id"
                )
            })

        return jsonify({
            "success": True,
            "count": len(matches),
            "matches": matches
        })

    except requests.exceptions.Timeout:

        return jsonify({
            "success": False,
            "error": "CricketData API timed out",
            "matches": []
        }), 504

    except requests.exceptions.RequestException as e:

        return jsonify({
            "success": False,
            "error": str(e),
            "matches": []
        }), 502

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e),
            "matches": []
        }), 500


@app.route("/live/<match_id>")
def get_match(match_id):

    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "CRICKET_API_KEY is not configured"
        }), 500

    try:

        response = requests.get(
            CURRENT_MATCHES_URL,
            params={
                "apikey": API_KEY,
                "offset": 0
            },
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "success":
            return jsonify({
                "success": False,
                "error": data.get(
                    "info",
                    "API error"
                )
            }), 502

        for match in data.get("data", []):

            if str(match.get("id")) == str(match_id):

                return jsonify({
                    "success": True,
                    "match": match
                })

        return jsonify({
            "success": False,
            "error": "Match not found"
        }), 404

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/debug")
def debug():

    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "CRICKET_API_KEY is missing"
        }), 500

    try:

        response = requests.get(
            CURRENT_MATCHES_URL,
            params={
                "apikey": API_KEY,
                "offset": 0
            },
            timeout=20
        )

        return jsonify({
            "success": response.ok,
            "http_status": response.status_code,
            "api_response": response.json()
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
```
