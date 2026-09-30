# Stable Render entrypoint for the cricket selector + OBS scoreboard.
#
# IMPORTANT: the production OBS route uses main.live_detail() directly.  The
# older wsgi/entry parser depended on helper functions that are not present in
# main.py, which caused Render logs such as:
#   AttributeError: module 'main' has no attribute 'scorecard_url'
#   AttributeError: module 'main' has no attribute 'team_code'
# Using the tolerant live JSON parser here avoids that failure path completely.

from flask import request
import selector_entry
import main

app = selector_entry.app


def _selected_score_fixed():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return selector_entry._fixed_selected_score()

    # Resolve the real Cricbuzz match URL/name from the selector whenever
    # possible. This keeps the selected match identity accurate.
    try:
        match = next(
            (m for m in selector_entry.get_matches() if str(m.get("id")) == mid),
            None,
        )
    except Exception as exc:
        print("match discovery for scoreboard failed:", repr(exc))
        match = None

    if match is None:
        match = {
            "id": mid,
            "name": f"Match {mid}",
            "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}",
        }

    data = None

    # Primary production parser: main.py talks directly to Cricbuzz's live
    # center endpoint and tolerantly extracts teams, score, batsmen, bowler,
    # captain data, flags and the current innings.
    try:
        data = main.live_detail(mid)
        data["url"] = match.get("url", "")
        data.setdefault("current_over", {"over": "", "balls": [], "free_hit": False, "last_ball": ""})
    except Exception as exc:
        print("main live parser failed:", repr(exc))

    # If the live center is temporarily unavailable, try the selector's
    # direct Cricbuzz JSON parser. This is only a fallback; it is never needed
    # for normal operation and does not call the broken scorecard helpers.
    if data is None:
        try:
            data = selector_entry._fallback_live(match)
        except Exception as exc:
            print("selector live fallback failed:", repr(exc))
            data = None

    if data is None:
        data = {
            "title": match.get("name", "CRICKET LIVE"),
            "url": match.get("url", ""),
            "team1": "LIVE DATA",
            "team2": "RETRYING",
            "team1_code": "",
            "team2_code": "",
            "team1_flag": "🏳️",
            "team2_flag": "🏳️",
            "team1_score": "-",
            "team2_score": "-",
            "team1_overs": "",
            "team2_overs": "",
            "crr": "-",
            "partnership": "-",
            "status": "LIVE DATA RETRYING",
            "batsmen": [],
            "bowler": None,
            "captains": [],
            "batting_index": 0,
            "bowling_index": 1,
            "current_over": {"over": "", "balls": [], "free_hit": False, "last_ball": ""},
        }

    data.setdefault("url", match.get("url", ""))
    data.setdefault("current_over", {"over": "", "balls": [], "free_hit": False, "last_ball": ""})
    data.setdefault("batsmen", [])
    data.setdefault("captains", [])
    data.setdefault("crr", "-")
    data.setdefault("partnership", "-")
    data.setdefault("status", "LIVE")
    data.setdefault("team1_score", "-")
    data.setdefault("team2_score", "-")
    data.setdefault("team1_overs", "")
    data.setdefault("team2_overs", "")
    data.setdefault("batting_index", 0)
    data.setdefault("bowling_index", 1 - int(data.get("batting_index", 0) or 0))

    response = selector_entry.jsonify({"match": data, "error": None})
    for key, value in {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Vary": "*",
    }.items():
        response.headers[key] = value
    return response


# Replace the /selected-score handler installed by selector_entry with the
# stable handler above while preserving the selector and scoreboard routes.
_selected_endpoint = next(
    (r.endpoint for r in app.url_map.iter_rules() if r.rule == "/selected-score"),
    None,
)
if _selected_endpoint:
    app.view_functions[_selected_endpoint] = _selected_score_fixed
else:
    app.add_url_rule(
        "/selected-score",
        endpoint="stable_selected_score",
        view_func=_selected_score_fixed,
        methods=["GET"],
    )


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
