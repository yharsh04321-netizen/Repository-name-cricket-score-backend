# Render entrypoint for the live match selector + production OBS scoreboard.
# This file deliberately reuses the production OBS app and only adds the selector.
from flask import Response, request, jsonify, redirect
from urllib.parse import quote
import re
import time
import requests
from bs4 import BeautifulSoup
import entry
import main

app = entry.app
HEADERS = dict(main.HEADERS)
HEADERS.update({
    "User-Agent": "Mozilla/5.0 (cricket-live-overlay/1.0)",
    "Cache-Control": "no-cache, no-store, max-age=0",
    "Pragma": "no-cache",
})
SELECTOR_SOURCES = [
    "https://www.cricbuzz.com/cricket-match/live-scores",
    "https://m.cricbuzz.com/cricket-match/live-scores",
]


def get_matches():
    matches, seen = [], set()
    for url in SELECTOR_SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                m = re.search(r"/live-cricket-scores/(\d+)(?:/([^?#\"]+))?", href)
                if not m:
                    continue
                mid, slug = m.group(1), (m.group(2) or "")
                if mid in seen:
                    continue
                text = " ".join(a.stripped_strings) or slug.replace("-", " ").title()
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 5 or "scorecard" in text.lower():
                    continue
                seen.add(mid)
                matches.append({
                    "id": mid,
                    "name": text[:180],
                    "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}/{slug}" if slug else f"https://www.cricbuzz.com/live-cricket-scores/{mid}",
                })
        except Exception as exc:
            print("selector source error:", repr(exc))
        if len(matches) >= 12:
            break

    # Keep the known current test match available if the source index omits it.
    if not any(str(x["id"]) == "151543" for x in matches):
        matches.insert(0, {
            "id": "151543",
            "name": "India vs West Indies — 2nd ODI",
            "url": "https://www.cricbuzz.com/live-cricket-scores/151543/ind-vs-wi-2nd-odi-india-v-west-indies",
        })
    return matches[:30]


def _fallback_live(match):
    """Build the exact scoreboard schema directly from Cricbuzz live JSON.
    This prevents the OBS page from being stuck at LOADING when the richer parser
    cannot resolve a scorecard snapshot or captain metadata.
    """
    mid = str(match["id"])
    url = main.scorecard_url(match.get("url", "")) if match.get("url") else f"https://www.cricbuzz.com/live-cricket-scores/{mid}"
    match = dict(match)
    match["url"] = url
    live_url = f"https://www.cricbuzz.com/api/mcenter/comm/{mid}?obs_ts={time.time_ns()}"
    try:
        r = requests.get(live_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print("fallback live fetch error:", repr(exc))
        return None

    mini = payload.get("miniscore") or {}
    header = payload.get("matchHeader") or {}
    t1 = main._team_name(header.get("team1")) if hasattr(main, "_team_name") else ""
    t2 = main._team_name(header.get("team2")) if hasattr(main, "_team2") else ""
    if not t1:
        t1 = (header.get("team1") or {}).get("teamName") or (header.get("team1") or {}).get("name") or "TEAM 1"
    if not t2:
        t2 = (header.get("team2") or {}).get("teamName") or (header.get("team2") or {}).get("name") or "TEAM 2"

    bat = mini.get("batTeam") or {}
    bat_obj = mini.get("batTeamScoreObj") or {}
    bat_name = bat_obj.get("teamName") or bat_obj.get("teamFullName") or bat_obj.get("name") or bat.get("teamName") or bat.get("teamShortName") or mini.get("batTeamName") or ""
    runs = bat.get("teamScore", bat.get("score", mini.get("teamScore")))
    wkts = bat.get("teamWkts", bat.get("wickets", mini.get("teamWkts")))
    overs = mini.get("overs", mini.get("oversStr", ""))
    if runs is None or wkts is None:
        return None

    def norm(v):
        return re.sub(r"[^a-z0-9]", "", str(v or "").lower())
    def team_match(a, b):
        a, b = norm(a), norm(b)
        return bool(a and b and (a == b or a in b or b in a))

    if team_match(bat_name, t1):
        bi = 0
    elif team_match(bat_name, t2):
        bi = 1
    else:
        bi = 0

    def player(obj, striker=False):
        if not isinstance(obj, dict):
            return None
        name = obj.get("batName") or obj.get("name") or obj.get("batsmanName")
        if not name:
            return None
        return {"name": str(name), "runs": str(obj.get("batRuns", obj.get("runs", obj.get("r", 0)))), "balls": str(obj.get("batBalls", obj.get("balls", obj.get("b", 0)))), "striker": bool(striker)}

    def bowler(obj):
        if not isinstance(obj, dict):
            return None
        name = obj.get("bowlName") or obj.get("name") or obj.get("bowlerName")
        if not name:
            return None
        return {"name": str(name), "overs": str(obj.get("bowlOvs", obj.get("overs", obj.get("o", "")))), "maidens": str(obj.get("bowlMaidens", obj.get("maidens", obj.get("m", 0)))), "runs": str(obj.get("bowlRuns", obj.get("runs", obj.get("r", 0)))), "wickets": str(obj.get("bowlWkts", obj.get("wickets", obj.get("w", 0)))), "economy": str(obj.get("bowlEcon", obj.get("economy", obj.get("eco", ""))))}

    bats = [x for x in [player(mini.get("batsmanStriker"), True), player(mini.get("batsmanNonStriker"), False)] if x]
    bo = bowler(mini.get("bowlerStriker") or mini.get("bowler") or mini.get("currentBowler"))
    partnership = mini.get("partnership") or mini.get("partnerShip") or mini.get("partnershipObj")
    if isinstance(partnership, dict):
        pr = partnership.get("runs", partnership.get("partnershipRuns", partnership.get("r")))
        pb = partnership.get("balls", partnership.get("partnershipBalls", partnership.get("b")))
        partnership = str(pr) + (f" ({pb})" if pb is not None else "") if pr is not None else "-"
    elif partnership is None:
        partnership = "-"
    else:
        partnership = str(partnership)

    try:
        crr = float(mini.get("currentRunRate", mini.get("crr")))
        crr = f"{crr:.2f}"
    except Exception:
        crr = str(mini.get("currentRunRate", mini.get("crr", "-")))

    flags = {"india": "🇮🇳", "westindies": "🌴", "australia": "🇦🇺", "england": "🏴", "pakistan": "🇵🇰", "southafrica": "🇿🇦", "srilanka": "🇱🇰", "bangladesh": "🇧🇩", "newzealand": "🇳🇿", "afghanistan": "🇦🇫"}
    def flag(team):
        return flags.get(norm(team), "🏳️")

    captains = []
    try:
        captains = entry.wsgi._captains(match, t1, t2) or []
    except Exception as exc:
        print("fallback captain parse error:", repr(exc))
    if len(captains) < 2:
        captains = (captains + [{"name": "Captain 1"}, {"name": "Captain 2"}])[:2]

    return {
        "title": f"{t1} vs {t2}", "url": url,
        "team1": t1, "team2": t2,
        "team1_code": main.team_code(t1), "team2_code": main.team_code(t2),
        "team1_flag": flag(t1), "team2_flag": flag(t2),
        "team1_score": f"{runs}-{wkts}" if bi == 0 else "-",
        "team2_score": f"{runs}-{wkts}" if bi == 1 else "-",
        "team1_overs": str(overs) if bi == 0 else "",
        "team2_overs": str(overs) if bi == 1 else "",
        "batting_index": bi, "bowling_index": 1 - bi,
        "batsmen": bats, "bowler": bo, "partnership": partnership, "crr": crr,
        "captains": captains,
        "status": str((header.get("status") or header.get("state") or mini.get("status") or "LIVE")),
        "current_over": {"over": "", "balls": [], "free_hit": False, "last_ball": ""},
    }


def _fixed_selected_score():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return jsonify({"match": None, "error": "match_id is required"}), 400
    match = next((m for m in get_matches() if str(m["id"]) == mid), None)
    if not match:
        match = {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}
    try:
        data = entry.wsgi._extract_live(match)
        if data is None:
            data = _fallback_live(match)
        if data is not None:
            try:
                data = entry._raw_score_fix(match, data)
            except Exception as exc:
                print("raw score fix skipped:", repr(exc))
        response = jsonify({"match": data, "error": None if data else "live score unavailable"})
    except Exception as exc:
        print("selected-score fatal error:", repr(exc))
        data = _fallback_live(match)
        response = jsonify({"match": data, "error": None if data else "live score temporarily unavailable"})
    for k, v in {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0", "Vary": "*"}.items():
        response.headers[k] = v
    return response


# Replace whichever /selected-score handler was installed by entry.py.
_selected_endpoint = next((r.endpoint for r in app.url_map.iter_rules() if r.rule == "/selected-score"), None)
if _selected_endpoint:
    app.view_functions[_selected_endpoint] = _fixed_selected_score
else:
    app.add_url_rule("/selected-score", endpoint="selector_selected_score", view_func=_fixed_selected_score, methods=["GET"])


def select_match():
    matches = get_matches()
    selected = str(request.args.get("selected", "")).strip()
    cards = []
    for m in matches:
        cards.append(f'''<div class="card"><div class="name">{main.escape_html(m["name"]) if hasattr(main, "escape_html") else m["name"]}</div><div class="id">Match ID: {m["id"]}</div><a class="btn" href="/select-match?selected={quote(str(m["id"]))}">SELECT THIS MATCH</a></div>''')
    chosen = next((m for m in matches if str(m["id"]) == selected), None)
    selected_html = ""
    if chosen:
        selected_html = f'''<div class="selected">✓ SELECTED: <b>{chosen["name"]}</b><br>Match ID: {chosen["id"]}<br><br><a href="/scoreboard?match_id={quote(str(chosen["id"]))}">OPEN LIVE SCOREBOARD</a></div>'''
    body = "".join(cards) or '<div class="empty">No live matches found. Tap REFRESH.</div>'
    html = f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Cache-Control" content="no-store"><title>Cricket Match Selector</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#0b0f14;color:#fff;font-family:Arial,sans-serif;padding:18px}}h1{{font-size:24px;margin:4px 0 6px}}.sub{{color:#9aa4b2;font-size:13px;margin-bottom:14px}}.card{{background:#151c25;border:1px solid #293443;border-radius:13px;padding:15px;margin:10px 0}}.name{{font-size:17px;font-weight:700;line-height:1.3}}.id{{color:#8d99a8;font-size:12px;margin:7px 0 12px}}.btn{{display:block;text-align:center;background:#00c853;color:#001b0a;text-decoration:none;font-weight:800;padding:12px;border-radius:9px}}.refresh{{display:inline-block;background:#00c853;color:#001b0a;text-decoration:none;font-weight:800;padding:11px 15px;border-radius:9px;margin:0 0 12px}}.selected{{background:#122a1b;border:1px solid #00c853;padding:14px;border-radius:10px;margin:10px 0 15px}}.selected a{{display:inline-block;background:#00c853;color:#001b0a;padding:11px 14px;border-radius:8px;text-decoration:none;font-weight:900}}.empty{{padding:30px 10px;text-align:center;color:#aab3bf}}</style></head><body><h1>🏏 Cricket Match Selector</h1><div class="sub">Choose the live match to send to the OBS scoreboard.</div><a class="refresh" href="/select-match">↻ REFRESH MATCHES</a>{selected_html}{body}</body></html>'''
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


_select_endpoint = next((r.endpoint for r in app.url_map.iter_rules() if r.rule == "/select-match"), None)
if _select_endpoint:
    app.view_functions[_select_endpoint] = select_match
else:
    app.add_url_rule("/select-match", endpoint="select_match", view_func=select_match, methods=["GET"])


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
