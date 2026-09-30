from flask import request
import re, html
import selector_entry, main

app = selector_entry.app
EMPTY = {"over":"","balls":[],"free_hit":False,"last_ball":""}

def txt(v):
    s=html.unescape(str(v or "")).replace("u003c","<").replace("u003e",">")
    return " ".join(re.sub(r"<[^>]+>"," ",s).split())

def label(r):
    e=str(r.get("event") or "").lower(); t=txt(r.get("commText") or r.get("commentary")).lower()
    x=r.get("ballLabel") or r.get("ball_label")
    if x not in (None,""): return str(x)
    if "wicket" in e:return "W"
    if "six" in e:return "6"
    if "four" in e:return "4"
    if "wide" in e:return "WD"
    if "noball" in e or "no_ball" in e or "no ball" in e:return "NB"
    if "legbye" in e or "leg bye" in e:return "LB"
    if re.search(r"\bbye\b",e):return "B"
    if re.search(r"\bno\s+runs?\b|\bno\s+run\b|\bdot\b",t):return "0"
    m=re.search(r"\b(\d+)\s+runs?\b",t)
    return m.group(1) if m else str(r.get("totalRuns",0))

def current_over(raw):
    rows=raw.get("matchCommentary") or raw.get("commentaryList") or []
    if isinstance(rows,dict): rows=rows.get("commentaryList") or rows.get("comments") or []
    items=[]
    for i,r in enumerate(rows if isinstance(rows,list) else []):
        if not isinstance(r,dict):continue
        try:m=float(r.get("ballMetric") or r.get("overNumber") or r.get("overNum"))
        except (TypeError,ValueError):continue
        if m<=0:continue
        try:ts=float(r.get("timestamp") or 0)
        except (TypeError,ValueError):ts=0
        items.append((ts,-i,m,str(r.get("inningsId",r.get("innings",""))),r))
    if not items:return dict(EMPTY)
    last=max(items); ov=int(last[2]); inn=last[3]; chosen={}
    for item in items:
        if int(item[2])!=ov or (inn and item[3] and item[3]!=inn):continue
        k=round(item[2],3)
        if k not in chosen or not txt(chosen[k][4].get("commText") or chosen[k][4].get("commentary")): chosen[k]=item
    balls=[{"label":label(x[4]),"ball":f"{x[2]:g}"} for x in sorted(chosen.values(),key=lambda x:x[2])]
    lt=txt(last[4].get("commText") or last[4].get("commentary")).lower()
    return {"over":str(ov),"balls":balls,"free_hit":"free hit" in lt or "freehit" in lt,"last_ball":balls[-1]["label"] if balls else ""}

def selected_score():
    mid=str(request.args.get("match_id","")).strip()
    if not mid.isdigit():return selector_entry._fixed_selected_score()
    try:match=next((m for m in selector_entry.get_matches() if str(m.get("id"))==mid),None)
    except Exception:match=None
    match=match or {"id":mid,"name":f"Match {mid}","url":f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}
    try:
        data=main.live_detail(mid);data["url"]=match.get("url","");data["current_over"]=current_over(main.fetch_live(mid))
    except Exception as exc:
        print("live parser/current-over error:",repr(exc))
        try:data=selector_entry._fallback_live(match)
        except Exception:data=None
    if data is None:data={"title":match.get("name","CRICKET LIVE"),"url":match.get("url",""),"team1":"LIVE DATA","team2":"RETRYING","team1_score":"-","team2_score":"-","team1_overs":"","team2_overs":"","crr":"-","partnership":"-","status":"LIVE DATA RETRYING","batsmen":[],"bowler":None,"captains":[],"batting_index":0}
    data.setdefault("current_over",dict(EMPTY));data.setdefault("batsmen",[]);data.setdefault("captains",[]);data.setdefault("crr","-");data.setdefault("partnership","-");data.setdefault("status","LIVE")
    data.setdefault("team1_score","-");data.setdefault("team2_score","-");data.setdefault("team1_overs","");data.setdefault("team2_overs","");data.setdefault("batting_index",0);data.setdefault("bowling_index",1-int(data.get("batting_index",0) or 0))
    resp=selector_entry.jsonify({"match":data,"error":None});resp.headers["Cache-Control"]="no-store, no-cache, max-age=0";return resp

ep=next((r.endpoint for r in app.url_map.iter_rules() if r.rule=="/selected-score"),None)
if ep:app.view_functions[ep]=selected_score
else:app.add_url_rule("/selected-score",endpoint="selected_score_fixed",view_func=selected_score,methods=["GET"])
