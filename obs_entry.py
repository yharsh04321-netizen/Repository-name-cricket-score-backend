# Stable Render entrypoint for the cricket selector + OBS scoreboard.
# Keeps the existing selector UI and replaces the broken selected-score route.
from flask import jsonify, request
import selector_entry
import entry
import wsgi

app = selector_entry.app


def _selected_score_fixed():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return jsonify({"match": None, "error": "match_id is required"}), 400

    match = {
        "id": mid,
        "name": f"Match {mid}",
        "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}",
    }

    try:
        data = wsgi._extract_live(match)
        if data is None:
            data = wsgi._fetch_match_detail(match)
        if data is None:
            data = wsgi._fallback_detail(match)

        try:
            data = entry._raw_score_fix(match, data)
        except Exception as exc:
            print("raw score fix skipped:", repr(exc))

        response = jsonify({"match": data, "error": None})
    except Exception as exc:
        print("stable selected-score error:", repr(exc))
        try:
            data = wsgi._fallback_detail(match)
        except Exception:
            data = {
                "title": "CRICKET LIVE", "team1": "TEAM 1", "team2": "TEAM 2",
                "team1_score": "-", "team2_score": "-", "team1_overs": "", "team2_overs": "",
                "batting_index": 0, "bowling_index": 1, "batsmen": [], "bowler": None,
                "captains": [], "crr": "-", "partnership": "-", "status": "DATA RETRYING",
                "current_over": {"over": "", "balls": [], "free_hit": False, "last_ball": ""},
            }
        response = jsonify({"match": data, "error": "live data retrying"})

    for key, value in {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache", "Expires": "0", "Vary": "*",
    }.items():
        response.headers[key] = value
    return response


for rule in list(app.url_map.iter_rules()):
    if rule.rule == "/selected-score":
        app.view_functions[rule.endpoint] = _selected_score_fixed
        break
else:
    app.add_url_rule("/selected-score", endpoint="stable_selected_score", view_func=_selected_score_fixed, methods=["GET"])
