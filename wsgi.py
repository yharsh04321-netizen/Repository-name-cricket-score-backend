"""Render entry point: live-data parser + full-screen OBS scoreboard."""
import re
import requests
from bs4 import BeautifulSoup
from flask import Response
import main


def _text(node):
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _parse_dom_players(html):
    if not html:
        return [], None
    soup = BeautifulSoup(html, "html.parser")
    innings = soup.find_all("div", id=re.compile(r"^innings?_\d+$", re.I))
    inning = innings[-1] if innings else soup
    batsmen = []
    for row in inning.select("div.cb-scrd-itms"):
        values = [_text(c) for c in row.find_all("div", recursive=False)]
        if len(values) >= 7 and values[2].isdigit() and values[3].isdigit():
            if values[0].lower() in {"batsman", "batting", "bowler", "bowling", "extras", "total"}:
                continue
            batsmen.append({"name": values[0].replace("*", "").strip(), "runs": values[2], "balls": values[3], "striker": "*" in values[0]})
    if batsmen:
        batsmen = batsmen[-2:]
    bowler = None
    rows = inning.select(".cb-col-bowlers .cb-scrd-itms") or soup.select(".cb-col-bowlers .cb-scrd-itms")
    for row in reversed(rows):
        values = [_text(c) for c in row.find_all("div", recursive=False)]
        if len(values) >= 5 and re.match(r"^\d+(?:\.\d+)?$", values[1]):
            bowler = {"name": values[0], "overs": values[1], "maidens": values[2], "runs": values[3], "wickets": values[4], "economy": values[5] if len(values) > 5 else ""}
            break
    return batsmen, bowler


def _improved_parse_players(text):
    section = main.clean(text[-20000:])
    bats = []
    for m in re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s*(\*)?\s*(\d+)\s*\((\d+)\)", section):
        name = main.clean(m.group(1))
        if name.lower() in {"over summary", "player of the match", "extras", "total"}:
            continue
        if not any(x["name"] == name for x in bats):
            bats.append({"name": name, "runs": m.group(3), "balls": m.group(4), "striker": bool(m.group(2))})
    if len(bats) < 2:
        for m in re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:Not out\s+|[^0-9]{1,80}\s+)?(\d+)\s+(\d+)\s+\d+\s+\d+\s+[0-9.]+", section, re.I):
            name = main.clean(m.group(1))
            if name.lower() in {"over summary", "player of the match", "extras", "total", "bowlers"}:
                continue
            if not any(x["name"] == name for x in bats):
                bats.append({"name": name, "runs": m.group(2), "balls": m.group(3), "striker": False})
            if len(bats) >= 2:
                break
    bowler = None
    candidates = list(re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)", section))
    for m in reversed(candidates):
        name = main.clean(m.group(1))
        if name.lower() in {"batsman", "batters", "bowler", "bowlers", "total", "extras"}:
            continue
        bowler = {"name": name, "overs": m.group(2), "maidens": m.group(3), "runs": m.group(4), "wickets": m.group(5), "economy": m.group(6)}
        break
    return bats[:2], bowler


def _extract_live_snapshot(match, html):
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    text = main.clean(soup.get_text(" ", strip=True))
    top = text[:14000]
    slug = re.search(r"/live-cricket-scores/\d+/([a-z0-9]+)-vs-([a-z0-9]+)", match.get("url", ""), re.I)
    codes = [x.upper() for x in slug.groups()] if slug else []
    if len(codes) != 2:
        return None

    found = []
    for idx, code in enumerate(codes):
        pat = rf"\b{re.escape(code)}(?:\s*\(\s*\d+(?:st|nd|rd|th)?\s+Inn(?:ings)?\s*\))?\s+(\d{{1,4}})\s*-\s*(\d{{1,2}})\s*\(\s*(\d+(?:\.\d+)?)\s*\)"
        m = re.search(pat, top, re.I)
        if m:
            found.append((idx, code, m))
    if not found:
        return None

    idx, code, score_match = min(found, key=lambda x: x[2].start())
    runs, wickets, overs = score_match.group(1), score_match.group(2), score_match.group(3)
    window = top[score_match.start():score_match.start() + 1800]
    crr = None
    partnership = None
    m = re.search(r"\bCRR\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)", window, re.I)
    if m:
        crr = m.group(1)
    m = re.search(r"P['’]?SHIP\s*[: ]\s*([0-9]+(?:\([0-9.]+\))?)", window, re.I)
    if m:
        partnership = m.group(1)
    return {"batting_index": idx, "team_code": code, "score": f"{runs}-{wickets}", "overs": overs, "crr": crr, "partnership": partnership}


def _apply_live_api_striker(match, batsmen):
    if not batsmen:
        return None
    match_url = match.get("url", "")
    mid_match = re.search(r"/(?:live-cricket-scores|live-cricket-scorecard)/(\d+)", match_url)
    if not mid_match:
        return None
    match_id = mid_match.group(1)
    api_url = f"https://www.cricbuzz.com/api/cricket-match/commentary/{match_id}"
    try:
        r = requests.get(api_url, headers=main.HEADERS, timeout=10)
        r.raise_for_status()
        payload = r.json()
        items = payload.get("commentaryList") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return None
        names = {main.norm_name(b.get("name", "")): b for b in batsmen if b.get("name")}
        striker_name = ""
        live_bowler = None
        for item in items:
            if not isinstance(item, dict):
                continue
            bs = item.get("batsmanStriker") or {}
            candidate = main.clean(bs.get("batName", ""))
            if candidate and main.norm_name(candidate) in names:
                striker_name = candidate
                bow = item.get("bowlerStriker") or {}
                if bow.get("bowlName"):
                    live_bowler = {"name": main.clean(bow.get("bowlName")), "overs": str(bow.get("bowlOvs", "")), "maidens": str(bow.get("bowlMaidens", "")), "runs": str(bow.get("bowlRuns", "")), "wickets": str(bow.get("bowlWkts", "")), "economy": str(bow.get("bowlEcon", ""))}
                break
        if not striker_name:
            return live_bowler
        target = main.norm_name(striker_name)
        for b in batsmen:
            b["striker"] = main.norm_name(b.get("name", "")) == target
        return live_bowler
    except Exception as exc:
        print("live API striker error:", exc)
        return None


_original_fetch = main.fetch_match_detail
main.parse_players = _improved_parse_players


def _patched_fetch_match_detail(match):
    data = _original_fetch(match)
    try:
        live_url = match.get("url", "")
        r_live = requests.get(live_url, headers=main.HEADERS, timeout=12)
        r_live.raise_for_status()
        snapshot = _extract_live_snapshot(match, r_live.text)
        if snapshot:
            idx = snapshot["batting_index"]
            data["batting_index"] = idx
            data["bowling_index"] = 0 if idx == 1 else 1
            data[f"team{idx + 1}_score"] = snapshot["score"]
            data[f"team{idx + 1}_overs"] = snapshot["overs"]
            if snapshot.get("crr"):
                data["crr"] = snapshot["crr"]
            if snapshot.get("partnership"):
                data["partnership"] = snapshot["partnership"]
            data["status"] = "LIVE"
    except Exception as exc:
        print("live score refresh error:", exc)

    if "batting_index" not in data:
        scores = []
        for key in ("team1_score", "team2_score"):
            s = str(data.get(key, ""))
            if re.match(r"^\d+-\d+$", s):
                scores.append(key)
        data["batting_index"] = 1 if len(scores) >= 2 else 0
        data["bowling_index"] = 0 if data["batting_index"] == 1 else 1

    idx = data["batting_index"]
    if not data.get("crr") or data.get("crr") == "-":
        score = str(data.get("team%d_score" % (idx + 1), ""))
        overs = str(data.get("team%d_overs" % (idx + 1), ""))
        sm = re.match(r"^(\d+)-\d+$", score)
        om = re.match(r"^(\d+)(?:\.(\d+))?$", overs)
        if sm and om:
            balls = int(om.group(1)) * 6 + int(om.group(2) or 0)
            if balls:
                data["crr"] = f"{int(sm.group(1)) / (balls / 6):.2f}"

    url = match.get("url", "").replace("/live-cricket-scores/", "/live-cricket-scorecard/")
    try:
        r = requests.get(url, headers=main.HEADERS, timeout=10)
        r.raise_for_status()
        bats, bowler = _parse_dom_players(r.text)
        if bats:
            data["batsmen"] = bats
        if bowler:
            data["bowler"] = bowler
    except Exception as exc:
        print("structured player fallback error:", exc)

    live_bowler = _apply_live_api_striker(match, data.get("batsmen") or [])
    if live_bowler:
        data["bowler"] = live_bowler
    return data


main.fetch_match_detail = _patched_fetch_match_detail
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
