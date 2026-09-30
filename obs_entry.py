# Stable Render entrypoint for the cricket selector + OBS scoreboard.
# The selector owns match discovery and the live-score route. This entrypoint
# must not replace that route with a weaker generic Match-ID fallback.
from flask import request
import selector_entry
import entry

app = selector_entry.app


def _selected_score_fixed():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return selector_entry._fixed_selected_score()

    # Reuse the same match metadata shown by the selector so the live parser
    # receives the real Cricbuzz URL/slug instead of "Match <id>".
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

    # Use the production parser first. If it cannot resolve the richer
    # scoreboard, use the selector's direct Cricbuzz JSON fallback. That
    # fallback understands miniscore.batTeamScoreObj as well as batTeam.
    try:
        data = entry.wsgi._extract_live(match)
    except Exception as exc:
        print("production live parser failed:", repr(exc))
        data = None

    if data is None:
        try:
            data = selector_entry._fallback_live(match)
        except Exception as exc:
            print("selector live fallback failed:", repr(exc))
            data = None

    # Last structured fallback: main.py's tolerant parser, which preserves
    # completed innings scores and captain/player data when Cricbuzz changes
    # the shape of miniscore.
    if data is None:
        try:
            data = entry.wsgi.main.live_detail(mid)
            data["url"] = match.get("url", "")
            data.setdefault("current_over", {"over": "", "balls": [], "free_hit": False, "last_ball": ""})
        except Exception as exc:
            print("main live parser failed:", repr(exc))
            data = None

    if data is None:
        # Never manufacture TEAM 1/TEAM 2 as though that were real match data.
        # Return the actual selected match identity and an explicit retry state.
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

    try:
        data = entry._raw_score_fix(match, data)
    except Exception as exc:
        print("raw score fix skipped:", repr(exc))

    # Ensure the overlay always has the fields its JS expects.
    data.setdefault("url", match.get("url", ""))
    data.setdefault("current_over", {"over": "", "balls": [], "free_hit": False, "last_ball": ""})
    data.setdefault("batsmen", [])
    data.setdefault("captains", [])
    data.setdefault("crr", "-")
    data.setdefault("partnership", "-")

    response = selector_entry.jsonify({"match": data, "error": None})
    for key, value in {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Vary": "*",
    }.items():
        response.headers[key] = value
    return response


# Replace the /selected-score handler installed by selector_entry with this
# stronger wrapper while preserving the selector and scoreboard routes.
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
