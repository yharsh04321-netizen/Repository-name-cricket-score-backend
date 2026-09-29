"""Render entry point for the OBS scoreboard."""
import re
import time
import requests
from bs4 import BeautifulSoup
from flask import Response
import main

LIVE_URL = "https://www.cricbuzz.com/api/mcenter/comm/{}"
LIVE_CACHE = {}
CAPTAIN_CACHE = {}
SCORECARD_CACHE = {}
CACHE_SECONDS = 4
SCORECARD_CACHE_SECONDS = 8
HEADERS = dict(main.HEADERS)
HEADERS["User-Agent"] = "Mozilla/5.0 cricket-live-overlay/1.0"


def _clean(value):
    return " ".join(str(value or "").split()).strip()


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", _clean(value).lower())


def _team_name(obj):
    if not isinstance(obj, dict):
        return ""
    for key in ("teamName", "teamFullName", "name", "team", "shortName", "teamShortName"):
        if obj.get(key):
            return _clean(obj[key])
    return ""


def _team_matches(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    aliases = {"indiaaw": "indwa", "australiaaw": "auswa", "indiaa": "inda", "australiaa": "ausa"}
    if aliases.get(a, a) == aliases.get(b, b):
        return True
    # Cricbuzz short codes such as INDWA/AUSWA versus full names.
    prefixes = (("ind", "india"), ("aus", "australia"), ("eng", "england"), ("pak", "pakistan"), ("ban", "bangladesh"), ("afg", "afghanistan"), ("rsa", "southafrica"))
    for code, name in prefixes:
        if (a.startswith(code) and b.startswith(name)) or (b.startswith(code) and a.startswith(name)):
            return True
    return False


def _player(obj, striker=False):
    if not isinstance(obj, dict):
        return None
    name = obj.get("batName") or obj.get("name") or obj.get("batsmanName")
    if not name:
        return None
    return {"name": _clean(name), "runs": str(obj.get("batRuns", obj.get("runs", obj.get("r", 0)))), "balls": str(obj.get("batBalls", obj.get("balls", obj.get("b", 0)))), "striker": bool(striker)}


def _bowler(obj):
    if not isinstance(obj, dict):
        return None
    name = obj.get("bowlName") or obj.get("name") or obj.get("bowlerName")
    if not name:
        return None
    return {"name": _clean(name), "overs": str(obj.get("bowlOvs", obj.get("overs", obj.get("o", "")))), "maidens": str(obj.get("bowlMaidens", obj.get("maidens", obj.get("m", 0)))), "runs": str(obj.get("bowlRuns", obj.get("runs", obj.get("r", 0)))), "wickets": str(obj.get("bowlWkts", obj.get("wickets", obj.get("w", 0)))), "economy": str(obj.get("bowlEcon", obj.get("economy", obj.get("eco", ""))))}


def _match_id(match):
    m = re.search(r"/(?:live-cricket-scores|live-cricket-scorecard)/(\d+)", match.get("url", ""))
    return m.group(1) if m else str(match.get("id", ""))


def _latest_commentary_items(payload):
    items = []
    for key in ("matchCommentary", "commentaryList"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            items.extend(x for x in value if isinstance(x, dict))
    return sorted(items, key=lambda x: x.get("timestamp", 0), reverse=True)


def _live_data(match):
    mid = _match_id(match)
    if not mid:
        return None
    now = time.time()
    cached = LIVE_CACHE.get(mid)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]
    try:
        r = requests.get(LIVE_URL.format(mid), headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        LIVE_CACHE[mid] = {"time": now, "data": data}
        return data
    except Exception as exc:
        print("live center error:", repr(exc))
        return cached["data"] if cached else None


def _scorecard_snapshot(match):
    mid = _match_id(match)
    now = time.time()
    cached = SCORECARD_CACHE.get(mid)
    if cached and now - cached["time"] < SCORECARD_CACHE_SECONDS:
        return cached["data"]
    try:
        url = main.scorecard_url(match.get("url", ""))
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = _clean(soup.get_text(" ", strip=True))
        data = {"text": text, "scores": main.parse_scores(text)}
        SCORECARD_CACHE[mid] = {"time": now, "data": data}
        return data
    except Exception as exc:
        print("scorecard snapshot error:", repr(exc))
        return cached["data"] if cached else None


def _resolve_batting_index(match, team1, team2, score, wickets, fallback):
    snapshot = _scorecard_snapshot(match)
    if not snapshot:
        return fallback
    target_runs = str(score)
    target_wickets = str(wickets)
    for item in snapshot.get("scores", []):
        if str(item.get("runs")) != target_runs or str(item.get("wickets")) != target_wickets:
            continue
        code = item.get("code", "")
        if _team_matches(code, team1):
            return 0
        if _team_matches(code, team2):
            return 1
    return fallback


def _captains(match, team1, team2):
    key = _norm(team1) + "|" + _norm(team2)
    cached = CAPTAIN_CACHE.get(key)
    if cached and time.time() - cached["time"] < 1800:
        return cached["data"]
    result = []
    try:
        url = main.scorecard_url(match.get("url", ""))
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        result = main.parse_captains(r.text, _clean(soup.get_text(" ", strip=True)))
    except Exception as exc:
        print("captain parse error:", repr(exc))

    t = _norm(team1) + " " + _norm(team2)
    title = _norm(match.get("name", ""))
    fallback = []
    if "india" in t and "australia" in t:
        if "women" in t or "indwa" in t or "auswa" in t:
            fallback = ["Anushka Sharma", "Nicole Faltum"] if "t20" in title else ["Yastika Bhatia", "Tahlia Wilson"]
        else:
            fallback = ["Devdutt Padikkal", "Peter Handscomb"]
    if fallback:
        fixed = []
        for wanted in fallback:
            found = next((c for c in result if _norm(c.get("name")) == _norm(wanted)), None)
            if not found:
                found = {"name": wanted, "image": "https://ui-avatars.com/api/?name=" + requests.utils.quote(wanted) + "&size=256&background=15263c&color=ffffff&bold=true&format=png"}
            fixed.append(found)
        result = fixed
    else:
        result = result[:2]
    CAPTAIN_CACHE[key] = {"time": time.time(), "data": result}
    return result


def _extract_live(match):
    payload = _live_data(match)
    if not payload:
        return None
    mini = payload.get("miniscore") or {}
    header = payload.get("matchHeader") or {}
    team1 = _team_name(header.get("team1"))
    team2 = _team_name(header.get("team2"))
    if not team1 or not team2:
        team1, team2 = main.extract_teams(match.get("name", ""))

    bat_obj = mini.get("batTeam") or {}
    bat_score_obj = mini.get("batTeamScoreObj") or {}
    batting_team = _team_name(bat_score_obj) or _team_name(bat_obj) or _clean(mini.get("batTeamName") or mini.get("batTeamShortName"))
    score = bat_obj.get("teamScore", bat_obj.get("score", mini.get("teamScore")))
    wickets = bat_obj.get("teamWkts", bat_obj.get("wickets", mini.get("teamWkts")))
    overs = mini.get("overs", mini.get("oversStr", ""))
    if score is None or wickets is None:
        return None

    if _team_matches(batting_team, team1):
        batting_index = 0
    elif _team_matches(batting_team, team2):
        batting_index = 1
    else:
        code1, code2 = main.team_code(team1), main.team_code(team2)
        batting_index = 0 if _norm(batting_team) in {_norm(code1), _norm(team1)} else 1

    # At innings break/stumps Cricbuzz can switch batTeam to the next innings
    # while teamScore/teamWkts and the batsmen still describe the completed
    # innings. The scorecard is authoritative for which team owns that score.
    batting_index = _resolve_batting_index(match, team1, team2, score, wickets, batting_index)

    striker = _player(mini.get("batsmanStriker"), True)
    non_striker = _player(mini.get("batsmanNonStriker"), False)
    latest = _latest_commentary_items(payload)
    if not striker or not non_striker:
        for item in latest:
            s = _player(item.get("batsmanStriker"), True)
            ns = _player(item.get("batsmanNonStriker"), False)
            if s or ns:
                striker = striker or s
                non_striker = non_striker or ns
                if striker and non_striker:
                    break
    batsmen = []
    if striker:
        batsmen.append(striker)
    if non_striker and (not striker or _norm(non_striker["name"]) != _norm(striker["name"])):
        batsmen.append(non_striker)

    live_bowler = _bowler(mini.get("bowlerStriker") or mini.get("bowler") or mini.get("currentBowler"))
    if not live_bowler:
        for item in latest:
            live_bowler = _bowler(item.get("bowlerStriker"))
            if live_bowler:
                break

    partnership = mini.get("partnership") or mini.get("partnerShip") or mini.get("partnershipObj")
    if isinstance(partnership, dict):
        pr = partnership.get("runs", partnership.get("partnershipRuns", partnership.get("r")))
        pb = partnership.get("balls", partnership.get("partnershipBalls", partnership.get("b")))
        partnership = str(pr) + (f" ({pb})" if pb is not None else "") if pr is not None else "-"
    elif partnership is None:
        partnership = "-"
    else:
        partnership = str(partnership)

    crr = mini.get("currentRunRate", mini.get("crr", "-"))
    result = {"title": f"{team1} vs {team2}", "url": match.get("url", ""), "team1": team1, "team2": team2, "team1_code": main.team_code(team1), "team2_code": main.team_code(team2), "team1_flag": main.team_flag(team1), "team2_flag": main.team_flag(team2), "team1_score": "-", "team2_score": "-", "team1_overs": "", "team2_overs": "", "crr": str(crr), "partnership": partnership, "status": _clean(mini.get("status") or header.get("status") or "LIVE"), "batsmen": batsmen[:2], "bowler": live_bowler, "captains": _captains(match, team1, team2), "batting_index": batting_index, "bowling_index": 1 - batting_index}
    result[f"team{batting_index + 1}_score"] = f"{score}-{wickets}"
    result[f"team{batting_index + 1}_overs"] = str(overs)
    return result


def _fallback_detail(match):
    t1, t2 = main.extract_teams(match.get("name", ""))
    return {"title": match.get("name", "CRICKET"), "url": match.get("url", ""), "team1": t1, "team2": t2, "team1_code": main.team_code(t1), "team2_code": main.team_code(t2), "team1_flag": main.team_flag(t1), "team2_flag": main.team_flag(t2), "team1_score": "-", "team2_score": "-", "team1_overs": "", "team2_overs": "", "crr": "-", "partnership": "-", "status": "DATA RETRYING", "batsmen": [], "bowler": None, "captains": _captains(match, t1, t2), "batting_index": 0, "bowling_index": 1}


def _fetch_match_detail(match):
    return _extract_live(match) or _fallback_detail(match)

main.fetch_match_detail = _fetch_match_detail
app = main.app


def _scoreboard_full():
    mid = main.request.args.get("match_id", "")
    if not mid:
        return Response("Select a match first: <a href='/select-match'>Match Selector</a>", mimetype="text/html")
    try:
        with open("static/scoreboard_full_v2.html", "r", encoding="utf-8") as f:
            html = f.read()
        return Response(html, mimetype="text/html")
    except Exception as exc:
        return Response("Scoreboard template error: " + str(exc), status=500, mimetype="text/plain")

app.view_functions["scoreboard"] = _scoreboard_full
