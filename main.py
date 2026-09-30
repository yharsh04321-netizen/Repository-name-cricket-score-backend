from flask import Flask, jsonify, Response, request
import requests, time, re
from urllib.parse import quote
from pathlib import Path

app = Flask(__name__)
LIVE_URL = "https://www.cricbuzz.com/api/mcenter/comm/{mid}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*", "Accept-Language": "en-US,en;q=0.9", "Cache-Control": "no-cache", "Pragma": "no-cache"}
CACHE_SECONDS = 2
cache, last_scores = {}, {}
FLAGS = {"india":"🇮🇳","west indies":"🌴","australia":"🇦🇺","south africa":"🇿🇦","england":"🏴","sri lanka":"🇱🇰","pakistan":"🇵🇰","bangladesh":"🇧🇩","afghanistan":"🇦🇫","new zealand":"🇳🇿","zimbabwe":"🇿🇼","ireland":"🇮🇪","nepal":"🇳🇵","oman":"🇴🇲","malaysia":"🇲🇾","hong kong":"🇭🇰","usa":"🇺🇸","canada":"🇨🇦","bermuda":"🇧🇲","nigeria":"🇳🇬","sierra leone":"🇸🇱"}

def clean(v): return " ".join(str(v or "").split()).strip()
def flag(name):
    n=clean(name).lower()
    for k,v in FLAGS.items():
        if k in n: return v
    return "🏳️"
def code(name):
    n=clean(name).upper()
    return {"INDIA":"IND","WEST INDIES":"WI","AUSTRALIA":"AUS","SOUTH AFRICA":"RSA","ENGLAND":"ENG","SRI LANKA":"SL","PAKISTAN":"PAK","BANGLADESH":"BAN","AFGHANISTAN":"AFG","NEW ZEALAND":"NZ","ZIMBABWE":"ZIM","IRELAND":"IRE"}.get(n,n[:5] or "T1")
def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj,list):
        for v in obj: yield from walk(v)
def obj_name(x):
    if isinstance(x,dict):
        for k in ("teamName","name","shortName","teamSName","team"):
            v=x.get(k)
            if isinstance(v,str) and v.strip(): return clean(v)
            if isinstance(v,dict):
                n=obj_name(v)
                if n:return n
    return clean(x) if isinstance(x,str) else ""
def norm_team(s):
    n=re.sub(r"[^a-z0-9]+","",clean(s).lower())
    return {"wi":"westindies","westindies":"westindies","ind":"india","india":"india"}.get(n,n)
def same_team(a,b):
    a,b=norm_team(a),norm_team(b)
    return bool(a and b and (a==b or a in b or b in a))
def teams_from_json(data):
    names=[]; h=data.get("matchHeader",{}) if isinstance(data,dict) else {}
    for key in ("team1","team2"):
        n=obj_name(h.get(key))
        if n and n not in names:names.append(n)
    if len(names)<2:
        for o in walk(h):
            if isinstance(o,dict):
                n=obj_name(o)
                if n and len(n)>2 and n not in names and ("teamId" in o or "teamSName" in o):names.append(n)
            if len(names)>=2:break
    if len(names)<2:
        bt=obj_name((data.get("miniscore") or {}).get("batTeam"))
        if bt and bt not in names:names.append(bt)
    return (names+["TEAM 2","TEAM 2"])[:2]
def fetch_live(mid):
    now=time.time(); c=cache.get(mid)
    if c and now-c["time"]<CACHE_SECONDS:return c["data"]
    r=requests.get(LIVE_URL.format(mid=mid),headers=HEADERS,timeout=12); r.raise_for_status()
    data=r.json(); cache[mid]={"time":now,"data":data}; return data
def score_from_obj(o):
    if not isinstance(o,dict):return None
    r=next((o.get(k) for k in ("teamScore","teamRuns","runs") if o.get(k) is not None and str(o.get(k)).strip()!=""),None)
    w=next((o.get(k) for k in ("teamWkts","wickets","teamWickets") if o.get(k) is not None and str(o.get(k)).strip()!=""),None)
    if r is None:return None
    try: float(str(r).replace(",",""))
    except: return None
    return f"{r}-{0 if w is None else w}"
def historical_scores(data,t1,t2):
    found={}
    for o in walk(data):
        if not isinstance(o,dict):continue
        names=[]
        for k in ("teamName","teamSName","batTeamName","bowlingTeamName","team","batTeam"):
            n=obj_name(o.get(k))
            if n:names.append(n)
        sc=score_from_obj(o)
        if not sc:continue
        for n in names:
            if same_team(n,t1):found["team1"]=sc
            if same_team(n,t2):found["team2"]=sc
    return found
def batting_team(ms):
    return obj_name(ms.get("batTeam")) or obj_name(ms.get("batTeamScoreObj")) or clean(ms.get("batTeamName"))

def live_detail(mid):
    data=fetch_live(mid); ms=data.get("miniscore") or {}; t1,t2=teams_from_json(data); bat=batting_team(ms)
    btso=ms.get("batTeamScoreObj") or {}; runs=btso.get("teamScore",ms.get("teamScore","-")); wkts=btso.get("teamWkts",ms.get("teamWkts",0))
    current_score=f"{runs}-{wkts}" if runs not in ("",None,"-") else "-"; overs=ms.get("overs","")
    state=last_scores.setdefault(mid,{"team1":"-","team2":"-","bat":""})
    for k,v in historical_scores(data,t1,t2).items():state[k]=v
    if bat and current_score!="-":
        if same_team(bat,t1):state["team1"]=current_score
        elif same_team(bat,t2):state["team2"]=current_score
        state["bat"]=bat
    striker=ms.get("batsmanStriker") or {}; non=ms.get("batsmanNonStriker") or {}
    bow=ms.get("bowlerStriker") or ms.get("bowler") or ms.get("currentBowler") or {}
    partnership=ms.get("partnership") or ms.get("partnershipScore") or "-"
    if isinstance(partnership,dict):partnership=partnership.get("runs",partnership.get("score","-"))
    status=clean(ms.get("status") or ms.get("matchStatus") or "LIVE"); cr=ms.get("currentRunRate",ms.get("crr","-"))
    def player(p,striker_flag):
        if not isinstance(p,dict):return None
        name=clean(p.get("name") or p.get("batName"))
        if not name:return None
        return {"name":name,"runs":p.get("runs",p.get("batRuns",0)),"balls":p.get("balls",p.get("batBalls",0)),"striker":striker_flag}
    bd=None
    if isinstance(bow,dict):
        name=clean(bow.get("name") or bow.get("bowlName"))
        if name:bd={"name":name,"overs":bow.get("overs",bow.get("bowlOvs","0")),"maidens":bow.get("maidens",bow.get("bowlMaidens","0")),"runs":bow.get("runs",bow.get("bowlRuns","0")),"wickets":bow.get("wickets",bow.get("bowlWkts","0")),"economy":bow.get("economy",bow.get("bowlEcon","0"))}
    return {"title":f"{t1} vs {t2}","team1":t1,"team2":t2,"team1_code":code(t1),"team2_code":code(t2),"team1_flag":flag(t1),"team2_flag":flag(t2),"team1_score":state["team1"],"team2_score":state["team2"],"team1_overs":overs if bat and same_team(bat,t1) else "","team2_overs":overs if bat and same_team(bat,t2) else "","batting_team":bat,"crr":cr,"partnership":partnership,"status":status,"last_updated":ms.get("responseLastUpdated"),"batsmen":[x for x in (player(striker,True),player(non,False)) if x],"bowler":bd,"captains":[]}

@app.route("/")
def home(): return jsonify({"service":"Cricket Live Score Backend","status":"online","success":True})
@app.route("/selected-match")
def selected_match():
    mid=request.args.get("match_id",""); match={"id":str(mid),"name":f"Match {mid}","url":f"https://www.cricbuzz.com/live-cricket-scores/{mid}"} if mid else None
    return jsonify({"success":True,"selected":bool(mid),"match":match})
@app.route("/selected-score")
def selected_score():
    mid=request.args.get("match_id","")
    if not mid.isdigit():return jsonify({"success":True,"selected":False})
    try:return jsonify({"success":True,"selected":True,"match":live_detail(mid)})
    except Exception as e:
        print("LIVE FETCH ERROR:",repr(e))
        return jsonify({"success":True,"selected":True,"match":{"team1":"LIVE DATA","team2":"RETRYING","team1_score":"-","team2_score":"-","team1_overs":"","team2_overs":"","crr":"-","partnership":"-","status":"RETRYING LIVE DATA","batsmen":[],"bowler":None,"captains":[]}})
@app.route("/select-match")
def select_match():
    mid=request.args.get("selected","151543"); board="/scoreboard?match_id="+quote(mid)
    html=f'''<!doctype html><html><body style="font-family:Arial;background:#111;color:white;padding:30px"><h1>🏏 Cricket Live Score</h1><p>Selected match ID: {mid}</p><a style="background:#00c853;color:white;padding:14px 20px;border-radius:8px;text-decoration:none" href="{board}">OPEN LIVE SCOREBOARD</a></body></html>'''
    return Response(html,mimetype="text/html")
@app.route("/scoreboard")
def scoreboard():
    mid=request.args.get("match_id","")
    if not mid:return Response("Missing match_id",status=400)
    html=Path("static/scoreboard_full.html").read_text(encoding="utf-8")
    old="const b=m.batsmen||[],c=m.captains||[],bo=m.bowler,b1=b[0]||{},b2=b[1]||{},bi=Number.isInteger(m.batting_index)?m.batting_index:((m.team2_score&&m.team2_score!=='-')?1:0),bowli=bi===1?0:1;"
    new="const b=m.batsmen||[],c=m.captains||[],bo=m.bowler,b1=b[0]||{},b2=b[1]||{},bt=(m.batting_team||'').toLowerCase(),bi=(bt&&((m.team1||'').toLowerCase().includes(bt)||(bt.includes((m.team1||'').toLowerCase()))))?0:((bt&&((m.team2||'').toLowerCase().includes(bt)||(bt.includes((m.team2||'').toLowerCase()))))?1:(Number.isInteger(m.batting_index)?m.batting_index:0)),bowli=bi===1?0:1;"
    html=html.replace(old,new)
    return Response(html,mimetype="text/html")
if __name__=="__main__":
    import os
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
