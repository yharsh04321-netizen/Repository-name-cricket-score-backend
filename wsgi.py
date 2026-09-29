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
    batsmen=[]
    for row in inning.select("div.cb-scrd-itms"):
        values=[_text(c) for c in row.find_all("div",recursive=False)]
        if len(values)>=7 and values[2].isdigit() and values[3].isdigit():
            if values[0].lower() in {"batsman","batting","bowler","bowling","extras","total"}: continue
            batsmen.append({"name":values[0].replace("*","").strip(),"runs":values[2],"balls":values[3],"striker":"*" in values[0]})
    if batsmen:
        batsmen=batsmen[-2:]
    bowler=None
    rows=inning.select(".cb-col-bowlers .cb-scrd-itms") or soup.select(".cb-col-bowlers .cb-scrd-itms")
    for row in reversed(rows):
        values=[_text(c) for c in row.find_all("div",recursive=False)]
        if len(values)>=5 and re.match(r"^\d+(?:\.\d+)?$",values[1]):
            bowler={"name":values[0],"overs":values[1],"maidens":values[2],"runs":values[3],"wickets":values[4],"economy":values[5] if len(values)>5 else ""}
            break
    return batsmen,bowler


def _improved_parse_players(text):
    section=main.clean(text[-20000:]); bats=[]
    for m in re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s*(\*)?\s*(\d+)\s*\((\d+)\)",section):
        name=main.clean(m.group(1))
        if name.lower() in {"over summary","player of the match","extras","total"}: continue
        if not any(x["name"]==name for x in bats):
            bats.append({"name":name,"runs":m.group(3),"balls":m.group(4),"striker":bool(m.group(2))})
    if len(bats)<2:
        for m in re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:Not out\s+|[^0-9]{1,80}\s+)?(\d+)\s+(\d+)\s+\d+\s+\d+\s+[0-9.]+",section,re.I):
            name=main.clean(m.group(1))
            if name.lower() in {"over summary","player of the match","extras","total","bowlers"}: continue
            if not any(x["name"]==name for x in bats): bats.append({"name":name,"runs":m.group(2),"balls":m.group(3),"striker":False})
            if len(bats)>=2: break
    bowler=None
    candidates=list(re.finditer(r"(?<!\w)([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)",section))
    for m in reversed(candidates):
        name=main.clean(m.group(1))
        if name.lower() in {"batsman","batters","bowler","bowlers","total","extras"}: continue
        bowler={"name":name,"overs":m.group(2),"maidens":m.group(3),"runs":m.group(4),"wickets":m.group(5),"economy":m.group(6)}; break
    return bats[:2],bowler

_original_fetch=main.fetch_match_detail
main.parse_players=_improved_parse_players


def _patched_fetch_match_detail(match):
    data=_original_fetch(match)
    # The score parser preserves innings order. For limited-overs matches, the
    # last score is the current innings once both innings are present; otherwise
    # the first score is the current innings.
    scores=[]
    for key in ("team1_score","team2_score"):
        s=str(data.get(key,""));
        if re.match(r"^\d+-\d+$",s): scores.append(key)
    data["batting_index"]=1 if len(scores)>=2 else 0
    data["bowling_index"]=0 if data["batting_index"]==1 else 1

    if not data.get("crr") or data.get("crr")=="-":
        idx=data["batting_index"]
        score=str(data.get("team%d_score"%(idx+1),"")); overs=str(data.get("team%d_overs"%(idx+1),""))
        sm=re.match(r"^(\d+)-\d+$",score); om=re.match(r"^(\d+)(?:\.(\d+))?$",overs)
        if sm and om:
            balls=int(om.group(1))*6+int(om.group(2) or 0)
            if balls: data["crr"]=f"{int(sm.group(1))/(balls/6):.2f}"

    if not data.get("batsmen") or not data.get("bowler"):
        url=match.get("url","").replace("/live-cricket-scores/","/live-cricket-scorecard/")
        try:
            r=requests.get(url,headers=main.HEADERS,timeout=10); r.raise_for_status()
            bats,bowler=_parse_dom_players(r.text)
            if bats: data["batsmen"]=bats
            if bowler: data["bowler"]=bowler
        except Exception as exc: print("structured player fallback error:",exc)
    return data

main.fetch_match_detail=_patched_fetch_match_detail
app=main.app

# Replace the older embedded /scoreboard page with the full-screen template.
def _scoreboard_full():
    mid=main.request.args.get("match_id","")
    if not mid:
        return Response("Select a match first: <a href='/select-match'>Match Selector</a>",mimetype="text/html")
    try:
        with open("static/scoreboard_full.html","r",encoding="utf-8") as f:
            html=f.read()
        return Response(html,mimetype="text/html")
    except Exception as exc:
        return Response("Scoreboard template error: "+str(exc),status=500,mimetype="text/plain")

app.view_functions["scoreboard"]=_scoreboard_full
