# Render production entrypoint for the OBS cricket scoreboard.
import time
import requests
import wsgi
from flask import request, jsonify, send_from_directory

app = wsgi.app

# Keep the latest raw Cricbuzz response fresh. Cricbuzz's live score is a
# polling endpoint; the site itself refreshes this data about every 5 seconds.
SCORE_MEMORY = {}


def _obs_fresh_live_data(match):
    mid = wsgi._match_id(match)
    if not mid:
        return None
    url = wsgi.LIVE_URL.format(mid) + "?obs_ts=" + str(time.time_ns())
    headers = dict(wsgi.HEADERS)
    headers.update({
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (cricket-live-overlay/1.0)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cricbuzz.com/",
        "Origin": "https://www.cricbuzz.com",
    })
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        wsgi.LIVE_CACHE[mid] = {"time": time.time(), "data": data}
        return data
    except Exception as exc:
        print("fresh live center error:", repr(exc))
        cached = wsgi.LIVE_CACHE.get(mid)
        return cached["data"] if cached else None


wsgi._live_data = _obs_fresh_live_data


def _valid_score(v):
    return v not in (None, "", "-")


def _raw_score_fix(match, data):
    """Fill score fields directly from miniscore.batTeam.

    The live JSON uses miniscore.batTeam.teamScore/teamWkts. Older code was
    looking primarily at batTeamScoreObj, which can be absent and produced a
    perfectly valid page with player/CRR data but '-' for the team score.
    """
    if not isinstance(data, dict):
        return data
    payload = _obs_fresh_live_data(match)
    if not isinstance(payload, dict):
        return data
    mini = payload.get("miniscore") or {}
    bat = mini.get("batTeam") or {}
    header = payload.get("matchHeader") or {}
    t1obj, t2obj = header.get("team1") or {}, header.get("team2") or {}
    t1 = wsgi._team_name(t1obj) or data.get("team1", "")
    t2 = wsgi._team_name(t2obj) or data.get("team2", "")
    bat_name = (wsgi._team_name(bat)
                or wsgi._team_name(mini.get("batTeamScoreObj") or {})
                or mini.get("batTeamName")
                or mini.get("batTeamShortName")
                or "")
    runs = bat.get("teamScore", bat.get("score", mini.get("teamScore")))
    wickets = bat.get("teamWkts", bat.get("wickets", mini.get("teamWkts")))
    overs = mini.get("overs", mini.get("oversStr", ""))
    if runs is None or wickets is None:
        return data
    score = f"{runs}-{wickets}"

    if wsgi._team_matches(bat_name, t1):
        idx = 0
    elif wsgi._team_matches(bat_name, t2):
        idx = 1
    else:
        idx = data.get("batting_index", 0)
        try:
            idx = int(idx)
        except Exception:
            idx = 0

    key = str(wsgi._match_id(match))
    mem = SCORE_MEMORY.setdefault(key, {"team1_score": "-", "team2_score": "-", "team1_overs": "", "team2_overs": ""})

    # During a normal live innings, attach the fresh score to the actual
    # batting team. Keep the other innings score intact.
    if idx == 0:
        mem["team1_score"] = score
        if overs != "": mem["team1_overs"] = str(overs)
    else:
        mem["team2_score"] = score
        if overs != "": mem["team2_overs"] = str(overs)

    # Never let a '-' from a transient response erase a score we already saw.
    if not _valid_score(data.get("team1_score")):
        data["team1_score"] = mem["team1_score"]
    if not _valid_score(data.get("team2_score")):
        data["team2_score"] = mem["team2_score"]
    if not data.get("team1_overs"):
        data["team1_overs"] = mem["team1_overs"]
    if not data.get("team2_overs"):
        data["team2_overs"] = mem["team2_overs"]

    # If wsgi produced no useful score at all, use the raw live score.
    if not _valid_score(data.get("team1_score")) and idx == 0:
        data["team1_score"] = score
    if not _valid_score(data.get("team2_score")) and idx == 1:
        data["team2_score"] = score

    data["team1"] = t1 or data.get("team1", "TEAM 1")
    data["team2"] = t2 or data.get("team2", "TEAM 2")
    data["batting_index"] = idx
    data["bowling_index"] = 1 - idx
    return data


def _obs_selected_score():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return jsonify({"match": None, "error": "match_id is required"}), 400
    try:
        match = wsgi.main.get_match_by_id(mid)
        # _extract_live uses the fresh payload and supplies batsmen, bowler,
        # current over and CRR. Then _raw_score_fix guarantees the score line.
        data = wsgi._extract_live(match)
        if data is None:
            data = wsgi._fetch_match_detail(match)
        data = _raw_score_fix(match, data)

        response = jsonify({"match": data})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Vary"] = "*"
        return response
    except Exception as exc:
        print("OBS selected-score error:", repr(exc))
        response = jsonify({"match": None, "error": "live score temporarily unavailable"})
        response.status_code = 200
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


# Replace the existing endpoint from main/wsgi with our fresh version.
_selected_endpoint = None
for _rule in app.url_map.iter_rules():
    if _rule.rule == "/selected-score":
        _selected_endpoint = _rule.endpoint
        break
if _selected_endpoint:
    app.view_functions[_selected_endpoint] = _obs_selected_score
else:
    app.add_url_rule("/selected-score", endpoint="selected_score", view_func=_obs_selected_score, methods=["GET"])


# Restore the original full OBS layout. The previous deployment changed the
# embedded /scoreboard template; this uses the project's existing full-v2
# template instead, so only the live-data logic changes.
def _obs_scoreboard():
    return send_from_directory("static", "scoreboard_full_v2.html")

for _rule in list(app.url_map.iter_rules()):
    if _rule.rule == "/scoreboard":
        app.view_functions[_rule.endpoint] = _obs_scoreboard
        break


@app.after_request
def _obs_live_no_cache(response):
    if request.path in ("/scoreboard", "/selected-score"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Vary"] = "*"
    return response
