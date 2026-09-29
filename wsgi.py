"""WSGI entry point with a safer live-score parser for the OBS scoreboard."""
import re
import requests
from bs4 import BeautifulSoup

import main


def _text(node):
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _parse_dom_players(html):
    """Read the current innings directly from Cricbuzz scorecard row structure."""
    if not html:
        return [], None
    soup = BeautifulSoup(html, "html.parser")

    innings = soup.find_all("div", id=re.compile(r"^innings?_\d+$", re.I))
    inning = innings[-1] if innings else soup

    batsmen = []
    for row in inning.select("div.cb-scrd-itms"):
        cols = row.find_all("div", recursive=False)
        values = [_text(c) for c in cols]
        if len(values) < 5:
            continue
        if values[0].lower() in {"batsman", "batting", "bowler", "bowling", "extras", "total"}:
            continue
        # Standard scorecard row: player, dismissal, R, B, 4s, 6s, SR
        if len(values) >= 7 and values[2].isdigit() and values[3].isdigit():
            name = values[0].replace("*", "").strip()
            if not name or name.lower() in {"extras", "total"}:
                continue
            batsmen.append({
                "name": name,
                "runs": values[2],
                "balls": values[3],
                "striker": "*" in values[0],
            })

    # Keep the two most relevant/current batting rows. Prefer not-out rows.
    if batsmen:
        not_out = []
        for row in inning.select("div.cb-scrd-itms"):
            vals = [_text(c) for c in row.find_all("div", recursive=False)]
            if len(vals) >= 7 and vals[0].lower() not in {"batsman", "batting"}:
                if any("not out" in v.lower() for v in vals[1:2]):
                    not_out.append(vals[0].replace("*", "").strip())
        if not_out:
            ordered = [b for n in not_out for b in batsmen if b["name"] == n]
            ordered += [b for b in batsmen if b not in ordered]
            batsmen = ordered
        batsmen = batsmen[-2:]

    bowler = None
    bowl_rows = inning.select(".cb-col-bowlers .cb-scrd-itms")
    if not bowl_rows:
        bowl_rows = soup.select(".cb-col-bowlers .cb-scrd-itms")
    for row in reversed(bowl_rows):
        cols = row.find_all("div", recursive=False)
        values = [_text(c) for c in cols]
        if len(values) >= 5 and values[1] and re.match(r"^\d+(?:\.\d+)?$", values[1]):
            if values[0].lower() in {"bowler", "bowlers"}:
                continue
            eco = values[5] if len(values) > 5 else ""
            bowler = {
                "name": values[0],
                "overs": values[1],
                "maidens": values[2] if len(values) > 2 else "0",
                "runs": values[3] if len(values) > 3 else "0",
                "wickets": values[4] if len(values) > 4 else "0",
                "economy": eco,
            }
            break

    return batsmen, bowler


def _improved_parse_players(text):
    """Text fallback for scorecards where DOM classes are unavailable."""
    section = main.clean(text[-20000:])
    bats = []

    # Prefer the compact live format: Player * 33 (28).
    for m in re.finditer(
        r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s*(\*)?\s*(\d+)\s*\((\d+)\)",
        section,
    ):
        name = main.clean(m.group(1)).strip()
        if name.lower() in {"over summary", "player of the match", "extras", "total"}:
            continue
        item = {"name": name, "runs": m.group(3), "balls": m.group(4), "striker": bool(m.group(2))}
        if not any(x["name"] == name for x in bats):
            bats.append(item)

    # Standard scorecard text: Player ... R B 4s 6s SR.
    if len(bats) < 2:
        for m in re.finditer(
            r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:Not out\s+|[^0-9]{1,80}\s+)?(\d+)\s+(\d+)\s+\d+\s+\d+\s+[0-9.]+",
            section,
            re.I,
        ):
            name = main.clean(m.group(1))
            if name.lower() in {"over summary", "player of the match", "extras", "total", "bowlers"}:
                continue
            if not any(x["name"] == name for x in bats):
                bats.append({"name": name, "runs": m.group(2), "balls": m.group(3), "striker": False})
            if len(bats) >= 2:
                break

    bowler = None
    # Bowling rows normally contain O M R W ECO; choose the last valid row.
    candidates = list(re.finditer(
        r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)",
        section,
    ))
    for m in reversed(candidates):
        name = main.clean(m.group(1))
        if name.lower() in {"batsman", "batters", "bowler", "bowlers", "total", "extras"}:
            continue
        bowler = {
            "name": name,
            "overs": m.group(2),
            "maidens": m.group(3),
            "runs": m.group(4),
            "wickets": m.group(5),
            "economy": m.group(6),
        }
        break
    return bats[:2], bowler


# Make the existing HTML parser more tolerant. The existing fetch_match_detail
# already supplies the live team scores and captain cards, so we only repair the
# player/run-rate fields here and leave the visual design untouched.
_original_fetch = main.fetch_match_detail
main.parse_players = _improved_parse_players


def _patched_fetch_match_detail(match):
    data = _original_fetch(match)

    # Derive CRR when the upstream page does not expose a CRR label.
    if not data.get("crr") or data.get("crr") == "-":
        candidates = []
        for score_key, over_key in (("team1_score", "team1_overs"), ("team2_score", "team2_overs")):
            score = str(data.get(score_key, ""))
            overs = str(data.get(over_key, ""))
            sm = re.match(r"^(\d+)-\d+$", score)
            om = re.match(r"^(\d+)(?:\.(\d+))?$", overs)
            if sm and om:
                balls = int(om.group(1)) * 6 + int(om.group(2) or 0)
                if balls:
                    candidates.append((balls, int(sm.group(1)) / (balls / 6)))
        if candidates:
            # The innings with more legal balls is normally the current innings.
            data["crr"] = f"{max(candidates, key=lambda x: x[0])[1]:.2f}"

    # If the text parser still missed the current players/bowler, fetch the same
    # scorecard page once and parse its structured rows directly.
    if not data.get("batsmen") or not data.get("bowler"):
        url = match.get("url", "")
        if "/live-cricket-scores/" in url:
            url = url.replace("/live-cricket-scores/", "/live-cricket-scorecard/", 1)
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

    return data


main.fetch_match_detail = _patched_fetch_match_detail
app = main.app
