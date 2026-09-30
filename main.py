from flask import Flask, jsonify, Response, request, redirect
import requests, time, json, re
from urllib.parse import quote

app = Flask(__name__)

LIVE_URL = "https://www.cricbuzz.com/api/mcenter/comm/{mid}"
MATCH_LIST_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
CACHE_SECONDS = 2
cache = {}
last_scores = {}

FLAGS = {
    "india":"🇮🇳","west indies":"🌴","australia":"🇦🇺","south africa":"🇿🇦",
    "england":"🏴","sri lanka":"🇱🇰","pakistan":"🇵🇰","bangladesh":"🇧🇩",
    "afghanistan":"🇦🇫","new zealand":"🇳🇿","zimbabwe":"🇿🇼","ireland":"🇮🇪",
    "nepal":"🇳🇵","oman":"🇴🇲","malaysia":"🇲🇾","hong kong":"🇭🇰",
    "usa":"🇺🇸","canada":"🇨🇦","bermuda":"🇧🇲","nigeria":"🇳🇬","sierra leone":"🇸🇱"
}

def clean(v):
    return " ".join(str(v or "").split()).strip()

def flag(name):
    n = clean(name).lower()
    for k, v in FLAGS.items():
        if k in n: return v
    return "🏳️"

def code(name):
    n = clean(name).upper()
    return {"INDIA":"IND","WEST INDIES":"WI","AUSTRALIA":"AUS","SOUTH AFRICA":"RSA",
            "ENGLAND":"ENG","SRI LANKA":"SL","PAKISTAN":"PAK","BANGLADESH":"BAN",
            "AFGHANISTAN":"AFG","NEW ZEALAND":"NZ","ZIMBABWE":"ZIM","IRELAND":"IRE"}.get(n, n[:5] or "T1")

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def obj_name(x):
    if isinstance(x, dict):
        for k in ("teamName","name","shortName","team"):
            v = x.get(k)
            if isinstance(v, str) and v.strip(): return clean(v)
            if isinstance(v, dict):
                n = obj_name(v)
                if n: return n
    return clean(x) if isinstance(x, str) else ""

def teams_from_json(data):
    names = []
    h = data.get("matchHeader", {}) if isinstance(data, dict) else {}
    for key in ("team1","team2"):
        n = obj_name(h.get(key))
        if n and n not in names: names.append(n)
    if len(names) < 2:
        for o in walk(h):
            if isinstance(o, dict):
                n = obj_name(o)
                if n and len(n) > 2 and n not in names and ("teamId" in o or "teamSName" in o):
                    names.append(n)
            if len(names) >= 2: break
    if len(names) < 2:
        m = data.get("miniscore", {})
        bt = obj_name(m.get("batTeam"))
        if bt and bt not in names: names.append(bt)
    return (names + ["TEAM 2","TEAM 2"])[:2]

def batting_team(ms):
    bt = ms.get("batTeam") or {}
    return obj_name(bt) or obj_name(ms.get("batTeamScoreObj")) or ""

def number(v, default=""):
    return default if v is None else v

def fetch_live(mid):
    now = time.time()
    c = cache.get(mid)
    if c and now - c["time"] < CACHE_SECONDS:
        return c["data"]
    r = requests.get(LIVE_URL.format(mid=mid), headers=HEADERS, timeout=12)
    r.raise_for_status()
    data = r.json()
    cache[mid] = {"time": now, "data": data}
    return data

def live_detail(mid):
    data = fetch_live(mid)
    ms = data.get("miniscore") or {}
    t1, t2 = teams_from_json(data)
    bat = batting_team(ms)
    btso = ms.get("batTeamScoreObj") or {}
    runs = btso.get("teamScore", ms.get("teamScore", "-"))
    wkts = btso.get("teamWkts", ms.get("teamWkts", "-"))
    overs = ms.get("overs", "")
    current_score = f"{runs}-{wkts}" if runs != "-" and wkts != "-" else "-"

    state = last_scores.setdefault(mid, {"team1": "-", "team2": "-", "bat": ""})
    # Store the score against the ACTUAL batting team. This fixes the old
    # bug where the first parsed score was always displayed as team1.
    if bat:
        if bat.lower() in t1.lower() or t1.lower() in bat.lower():
            state["team1"] = current_score
        elif bat.lower() in t2.lower() or t2.lower() in bat.lower():
            state["team2"] = current_score
        state["bat"] = bat

    striker = ms.get("batsmanStriker") or {}
    non = ms.get("batsmanNonStriker") or {}
    bow = ms.get("bowler") or ms.get("currentBowler") or {}
    partnership = ms.get("partnership") or ms.get("partnershipScore") or "-"
    if isinstance(partnership, dict):
        partnership = partnership.get("runs", partnership.get("score", "-"))
    status = clean(ms.get("status") or ms.get("matchStatus") or "LIVE")
    cr = ms.get("currentRunRate", ms.get("crr", "-"))

    def player(p, striker_flag):
        if not isinstance(p, dict) or not p.get("name"): return None
        return {"name": clean(p.get("name")), "runs": number(p.get("runs"),0),
                "balls": number(p.get("balls"),0), "striker": striker_flag}

    bd = None
    if isinstance(bow, dict) and bow.get("name"):
        bd = {"name":clean(bow.get("name")),
              "overs":number(bow.get("overs"),"0"),
              "maidens":number(bow.get("maidens"),"0"),
              "runs":number(bow.get("runs"),"0"),
              "wickets":number(bow.get("wickets"),"0"),
              "economy":number(bow.get("economy"),"0")}

    return {
        "title": f"{t1} vs {t2}",
        "team1": t1, "team2": t2,
        "team1_code": code(t1), "team2_code": code(t2),
        "team1_flag": flag(t1), "team2_flag": flag(t2),
        "team1_score": state["team1"], "team2_score": state["team2"],
        "team1_overs": overs if state["bat"] and (state["bat"].lower() in t1.lower() or t1.lower() in state["bat"].lower()) else "",
        "team2_overs": overs if state["bat"] and (state["bat"].lower() in t2.lower() or t2.lower() in state["bat"].lower()) else "",
        "batting_team": bat, "crr": cr, "partnership": partnership,
        "status": status, "last_updated": ms.get("responseLastUpdated"),
        "batsmen": [x for x in (player(striker, True), player(non, False)) if x],
        "bowler": bd, "captains": []
    }

def fallback_match(mid):
    return {"id":str(mid),"name":f"Match {mid}","url":f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}

@app.route("/")
def home():
    return jsonify({"service":"Cricket Live Score Backend","status":"online","success":True})

@app.route("/selected-match")
def selected_match():
    mid = request.args.get("match_id","")
    return jsonify({"success":True,"selected":bool(mid),"match":fallback_match(mid) if mid else None})

@app.route("/selected-score")
def selected_score():
    mid = request.args.get("match_id","")
    if not mid.isdigit():
        return jsonify({"success":True,"selected":False})
    try:
        return jsonify({"success":True,"selected":True,"match":live_detail(mid)})
    except Exception as e:
        print("LIVE FETCH ERROR:", repr(e))
        return jsonify({"success":True,"selected":True,"match":{
            "team1":"LIVE DATA","team2":"RETRYING","team1_score":"-","team2_score":"-",
            "team1_overs":"","team2_overs":"","crr":"-","partnership":"-",
            "status":"RETRYING LIVE DATA","batsmen":[],"bowler":None,"captains":[]
        }})

@app.route("/select-match")
def select_match():
    mid = request.args.get("selected","151543")
    board = "/scoreboard?match_id=" + quote(mid)
    html = f'''<!doctype html><html><body style="font-family:Arial;background:#111;color:white;padding:30px">
    <h1>🏏 Cricket Live Score</h1><p>Selected match ID: {mid}</p>
    <a style="background:#00c853;color:white;padding:14px 20px;border-radius:8px;text-decoration:none" href="{board}">OPEN LIVE SCOREBOARD</a>
    </body></html>'''
    return Response(html,mimetype="text/html")

@app.route("/scoreboard")
def scoreboard():
    mid = request.args.get("match_id","")
    if not mid:
        return Response("Missing match_id",status=400)
    MID = json.dumps(mid)
    html = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Live Cricket Score</title><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent;font-family:Arial;color:#fff}
.wrap{width:100vw;height:100vh;padding:1vw}.board{height:100%;display:flex;flex-direction:column;overflow:hidden;border-radius:16px;background:#07111f}
.hero{height:48%;display:grid;grid-template-columns:1fr 1.35fr 1fr;background:linear-gradient(110deg,#062d54,#081426 50%,#280913)}
.side{display:flex;align-items:center;gap:1vw;padding:2vw}.right{justify-content:flex-end;text-align:right}
.flag{font-size:3vw;background:#fff;color:#111;border-radius:50%;padding:1vw}.team{font-size:2.2vw;font-weight:900;text-transform:uppercase}.score{font-size:5vw;font-weight:900;color:#ffd21a}.overs{font-size:1.2vw}
.mid{margin:1vw;padding:1vw;border-radius:14px;background:linear-gradient(145deg,#a80e1d,#ef1e35,#9f0d1c);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.battle{font-size:1.5vw;font-weight:900}.caps{display:flex;align-items:center;gap:.5vw;margin:1vw}.cap{background:#102844;border:2px solid #7ac7ff;border-radius:10px;padding:1vw;font-weight:900}.vs{background:#ffd21a;color:#4d0710;border-radius:50%;padding:.6vw;font-weight:900}.status{font-size:.9vw}
.info{height:10%;display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;text-align:center;background:#c91528;font-weight:900;font-size:1.3vw}
.cards{flex:1;display:grid;grid-template-columns:1.2fr 1.2fr 1fr;gap:3px}.card{padding:1.2vw;background:#087cb8}.red{background:#a8173a}.label{font-size:1vw;font-weight:900}.pname{font-size:2vw;font-weight:900;margin-top:.5vw}.pstat{font-size:2.3vw;color:#ffd21a;font-weight:900}.sub{font-size:.9vw}.footer{height:5%;display:flex;justify-content:space-between;align-items:center;padding:0 1vw;background:#02050a;font-size:.8vw}
@media(max-width:900px){.team{font-size:3vw}.score{font-size:7vw}.overs{font-size:1.7vw}.battle{font-size:2.4vw}.status{font-size:1.2vw}.info{font-size:1.8vw}.pname{font-size:2.7vw}.pstat{font-size:3vw}.label{font-size:1.4vw}.sub{font-size:1.2vw}}
</style></head><body><div class="wrap"><div class="board">
<div class="hero"><div class="side"><div class="flag" id="flag1">🏳️</div><div><div class="team" id="team1">TEAM 1</div><div class="score" id="score1">-</div><div class="overs" id="over1">-</div></div></div>
<div class="mid"><div class="battle">LIVE CRICKET</div><div class="caps"><div class="cap" id="cap1">LIVE</div><div class="vs">VS</div><div class="cap" id="cap2">LIVE</div></div><div class="status" id="status">CONNECTING...</div></div>
<div class="side right"><div><div class="team" id="team2">TEAM 2</div><div class="score" id="score2">-</div><div class="overs" id="over2">-</div></div><div class="flag" id="flag2">🏳️</div></div></div>
<div class="info"><div>CRR <b id="crr">-</b></div><div>P'SHIP <b id="partnership">-</b></div><div id="batting">LIVE</div></div>
<div class="cards"><div class="card"><div class="label">BATTER 1</div><div class="pname" id="bat1">-</div><div class="pstat" id="bat1score">-</div><div class="sub" id="bat1stats">-</div></div>
<div class="card"><div class="label">BATTER 2</div><div class="pname" id="bat2">-</div><div class="pstat" id="bat2score">-</div><div class="sub" id="bat2stats">-</div></div>
<div class="card red"><div class="label">BOWLER • LIVE</div><div class="pname" id="bowler">-</div><div class="pstat" id="bowlerscore">-</div><div class="sub" id="bowlerstats">-</div></div></div>
<div class="footer"><div id="last">WAITING...</div><div>🟢 LIVE AUTO UPDATE</div></div>
</div></div><script>
const MID=__MID__, $=id=>document.getElementById(id);
const set=(id,v)=>$(id).textContent=(v===undefined||v===null||v==="")?"-":v;
async function update(){
 try{
  const r=await fetch("/selected-score?match_id="+encodeURIComponent(MID)+"&t="+Date.now(),{cache:"no-store"});
  const d=await r.json(); if(!d.selected) return;
  const m=d.match||{};
  set("team1",m.team1);set("team2",m.team2);set("flag1",m.team1_flag);set("flag2",m.team2_flag);
  set("score1",m.team1_score);set("score2",m.team2_score);set("over1",m.team1_overs?m.team1_overs+" OVERS":"");set("over2",m.team2_overs?m.team2_overs+" OVERS":"");
  set("crr",m.crr);set("partnership",m.partnership);set("status",m.status);set("batting",(m.batting_team||"LIVE")+" BATTING");
  const b=m.batsmen||[]; set("bat1",b[0]?.name);set("bat1score",b[0]?`${b[0].runs} (${b[0].balls})`:"-");set("bat1stats",b[0]?.striker?"ON STRIKE":"NOT OUT");
  set("bat2",b[1]?.name);set("bat2score",b[1]?`${b[1].runs} (${b[1].balls})`:"-");set("bat2stats",b[1]?.striker?"ON STRIKE":"NOT OUT");
  if(m.bowler){set("bowler",m.bowler.name);set("bowlerscore",`${m.bowler.overs}-${m.bowler.maidens}-${m.bowler.runs}-${m.bowler.wickets}`);set("bowlerstats","ECO "+m.bowler.economy)}else{set("bowler","-");set("bowlerscore","-");}
  set("last","LAST UPDATE: "+new Date().toLocaleTimeString());
 }catch(e){set("status","RETRYING LIVE DATA");set("last","Connection retrying...")}
}
update();setInterval(update,5000);
</script></body></html>'''.replace("__MID__",MID)
    return Response(html,mimetype="text/html")

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
