from flask import Flask, jsonify, Response, request, redirect
import requests
from bs4 import BeautifulSoup
from html import escape
import re
import time
from urllib.parse import quote

app = Flask(__name__)
CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
detail_cache = {}
CACHE_SECONDS = 5
FLAGS = {"india":"🇮🇳","west indies":"🌴","australia":"🇦🇺","south africa":"🇿🇦","england":"🏴","sri lanka":"🇱🇰","pakistan":"🇵🇰","hong kong":"🇭🇰","afghanistan":"🇦🇫","bangladesh":"🇧🇩","malaysia":"🇲🇾","nepal":"🇳🇵","zimbabwe":"🇿🇼","new zealand":"🇳🇿","ireland":"🇮🇪","scotland":"🏴","netherlands":"🇳🇱","usa":"🇺🇸","oman":"🇴🇲","canada":"🇨🇦","bermuda":"🇧🇲","cayman islands":"🇰🇾","nigeria":"🇳🇬","sierra leone":"🇸🇱"}

def clean(v):
    return " ".join(str(v or "").split()).strip()

def absolute_url(url):
    if not url: return ""
    return url if url.startswith("http") else "https://www.cricbuzz.com" + url

def jina_url(url):
    return "https://r.jina.ai/http://" + url.removeprefix("https://").removeprefix("http://")

def team_flag(name):
    low = clean(name).lower()
    for key, flag in FLAGS.items():
        if key in low: return flag
    return "🏳️"

def team_code(name):
    n = clean(name).upper()
    codes = {"INDIA":"IND","WEST INDIES":"WI","AUSTRALIA":"AUS","SOUTH AFRICA":"RSA","ENGLAND":"ENG","SRI LANKA":"SL","PAKISTAN":"PAK","HONG KONG":"HK","AFGHANISTAN":"AFG","BANGLADESH":"BAN","MALAYSIA":"MAL","NEPAL":"NEP","ZIMBABWE":"ZIM","NEW ZEALAND":"NZ","IRELAND":"IRE","OMAN":"OMA","USA":"USA","CANADA":"CAN","BERMUDA":"BER","NIGERIA":"NGR","SIERRA LEONE":"SLE","CAYMAN ISLANDS":"CAY"}
    return codes.get(n, "".join(x[0] for x in n.split()[:3])[:5] or "T1")

def extract_teams(title):
    title = clean(title)
    m = re.search(r"(.+?)\s+vs\s+(.+?)(?:\s+-\s+|,\s*|$)", title, re.I)
    return (clean(m.group(1)), clean(m.group(2))) if m else ("TEAM 1","TEAM 2")

def fetch_matches():
    matches, seen = [], set()
    def add(name, url=""):
        name, url = clean(name).strip(" -*|#"), absolute_url(url)
        if len(name) < 5: return
        stable = re.search(r"/live-cricket-scores/(\d+)", url)
        match_id = stable.group(1) if stable else str(len(matches))
        if match_id in seen: return
        seen.add(match_id)
        matches.append({"id":match_id,"name":name[:250],"url":url})
    for source in (CRICBUZZ_URL, jina_url(CRICBUZZ_URL)):
        try:
            r = requests.get(source, headers=HEADERS, timeout=12); r.raise_for_status()
            soup = BeautifulSoup(r.text,"html.parser")
            for a in soup.select('a[href*="/live-cricket-scores/"]'):
                add(" ".join(a.stripped_strings), a.get("href",""))
            if matches: return matches
        except Exception as e: print("match list error:",e)
    return matches

def get_match_by_id(match_id):
    return next((m for m in fetch_matches() if str(m["id"]) == str(match_id)), None)

def parse_scores(text):
    patterns = [
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*/\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)",
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*-\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)",
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*\(\s*(\d+(?:\.\d+)?)"
    ]
    found=[]
    for p in patterns:
        for m in re.finditer(p,text[:12000]):
            item={"code":m.group(1),"runs":m.group(2),"wickets":"0","overs":m.group(3)}
            if len(m.groups())>=4: item["wickets"],item["overs"]=m.group(3),m.group(4)
            if item not in found: found.append(item)
    return found[:4]

def parse_players(text):
    section=text[-12000:]; bats=[]
    for m in re.finditer(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+)\s*\((\d+)\)",section):
        name=clean(m.group(1))
        if name.lower() in {"over summary","player of the match"}: continue
        if not any(x["name"]==name for x in bats): bats.append({"name":name,"runs":m.group(2),"balls":m.group(3)})
        if len(bats)==2: break
    bowler=None
    m=re.search(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)-(\d+)-(\d+)-(\d+(?:\.\d+)?)\b",section)
    if m: bowler={"name":clean(m.group(1)),"overs":m.group(2),"maidens":m.group(3),"runs":m.group(4),"wickets":m.group(5),"economy":m.group(6)}
    return bats,bowler

def fetch_match_detail(match):
    match_id=str(match["id"]); now=time.time(); cached=detail_cache.get(match_id)
    if cached and now-cached["time"]<CACHE_SECONDS: return cached["data"]
    team1,team2=extract_teams(match["name"])
    result={"title":match["name"],"url":match["url"],"team1":team1,"team2":team2,"team1_code":team_code(team1),"team2_code":team_code(team2),"team1_flag":team_flag(team1),"team2_flag":team_flag(team2),"team1_score":"-","team2_score":"-","team1_overs":"","team2_overs":"","crr":"-","partnership":"-","status":"WAITING FOR LIVE DATA","batsmen":[],"bowler":None}
    text=""
    try:
        r=requests.get(match["url"],headers=HEADERS,timeout=9); r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser"); text=clean(soup.get_text(" ",strip=True))
    except Exception as e: print("direct detail error:",e)
    if not re.search(r"\b[A-Z]{2,6}\s+\d{1,4}\s*(?:/|-)\s*\d+\s*\(",text[:12000]):
        try:
            r=requests.get(jina_url(match["url"]),headers={"User-Agent":HEADERS["User-Agent"]},timeout=10); r.raise_for_status(); text=clean(r.text)
        except Exception as e: print("jina detail error:",e)
    scores=parse_scores(text)
    if scores: result["team1_score"]=f"{scores[0]['runs']}-{scores[0]['wickets']}"; result["team1_overs"]=scores[0]["overs"]
    if len(scores)>1: result["team2_score"]=f"{scores[1]['runs']}-{scores[1]['wickets']}"; result["team2_overs"]=scores[1]["overs"]
    m=re.search(r"\bCRR\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)",text,re.I)
    if m: result["crr"]=m.group(1)
    m=re.search(r"P['’]?SHIP\s*[: ]\s*([0-9]+(?:\([0-9.]+\))?)",text,re.I)
    if m: result["partnership"]=m.group(1)
    for pat in (r"Match abandoned without toss",r"[A-Za-z ]+ won by \d+ runs",r"Innings Break",r"Day \d+: Stumps[^.]*"):
        m=re.search(pat,text,re.I)
        if m: result["status"]=clean(m.group(0)); break
    else:
        if scores: result["status"]="LIVE"
    result["batsmen"],result["bowler"]=parse_players(text)
    detail_cache[match_id]={"time":now,"data":result}
    return result

@app.route("/")
def home(): return jsonify({"service":"Cricket Live Score Backend","status":"online","success":True})

@app.route("/live-scores")
def live_scores():
    matches=fetch_matches()
    return jsonify({"success":True,"count":len(matches),"matches":matches})

@app.route("/select-match",methods=["GET","POST"])
def select_match():
    matches=fetch_matches()
    if request.method=="POST":
        mid=request.form.get("match_id","")
        if any(str(m["id"])==str(mid) for m in matches): return redirect("/select-match?selected="+quote(str(mid)))
    selected_id=request.args.get("selected","")
    selected=next((m for m in matches if str(m["id"])==str(selected_id)),None)
    cards="".join(f'''<div class="match"><div class="live">● LIVE / MATCH</div><div class="name">{escape(m["name"])}</div><form method="POST"><input type="hidden" name="match_id" value="{escape(m["id"])}"><button>SELECT THIS MATCH</button></form></div>''' for m in matches)
    if not cards: cards='<div class="empty">No matches found right now.</div>'
    selected_html=""
    if selected:
        board="/scoreboard?match_id="+quote(str(selected["id"]))
        selected_html=f'''<div class="selected">✓ SELECTED MATCH<br><br><strong>{escape(selected["name"])}</strong><br><br>OBS scoreboard URL:<br><br><code>{escape(board)}</code><br><br><a href="{escape(board)}">OPEN SCOREBOARD</a></div>'''
    html=f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Select Match</title><style>body{{margin:0;background:#101010;color:#fff;font-family:Arial}}.container{{max-width:900px;margin:30px auto;padding:20px}}.match{{background:#1d1d1d;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:15px}}.live{{color:#00e676;font-size:13px;font-weight:bold;margin-bottom:10px}}.name{{font-size:19px;font-weight:bold;margin-bottom:18px}}button,a{{background:#00c853;color:#fff;border:0;border-radius:7px;padding:12px 20px;font-weight:bold;text-decoration:none;display:inline-block}}.refresh{{background:#333;margin-bottom:20px}}.selected{{background:#12351f;border:1px solid #00c853;border-radius:10px;padding:20px;margin-bottom:20px}}.empty{{background:#1d1d1d;padding:30px;text-align:center;color:#aaa;border-radius:10px}}code{{background:#000;padding:5px 8px;border-radius:5px}}</style></head><body><div class="container"><h1>🏏 CRICKET LIVE SCORE</h1><p>Select today's match for your OBS scoreboard.</p>{selected_html}<button class="refresh" onclick="location.href='/select-match'">↻ REFRESH MATCHES</button>{cards}</div></body></html>'''
    return Response(html,mimetype="text/html")

@app.route("/selected-match")
def selected_match_api():
    mid=request.args.get("match_id",""); m=get_match_by_id(mid) if mid else None
    return jsonify({"success":True,"selected":bool(m),"match":m})

@app.route("/selected-score")
def selected_score():
    mid=request.args.get("match_id",""); m=get_match_by_id(mid) if mid else None
    if not m: return jsonify({"success":True,"selected":False,"message":"No match selected"})
    try: return jsonify({"success":True,"selected":True,"match":fetch_match_detail(m)})
    except Exception as e:
        print("selected score error:",e); t1,t2=extract_teams(m["name"])
        return jsonify({"success":True,"selected":True,"match":{"title":m["name"],"team1":t1,"team2":t2,"team1_code":team_code(t1),"team2_code":team_code(t2),"team1_flag":team_flag(t1),"team2_flag":team_flag(t2),"team1_score":"-","team2_score":"-","team1_overs":"","team2_overs":"","crr":"-","partnership":"-","status":"LIVE DATA TEMPORARILY UNAVAILABLE","batsmen":[],"bowler":None}})

@app.route("/scoreboard")
def scoreboard():
    mid=request.args.get("match_id","")
    if not mid: return Response("<html><body style='font-family:Arial;padding:30px'>Select a match first. Open <a href='/select-match'>Match Selector</a>.</body></html>",mimetype="text/html")
    html='''<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OBS Cricket Scoreboard</title><style>*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:transparent!important;overflow:hidden;font-family:Arial;color:#fff}#board{position:absolute;left:2%;right:2%;bottom:2%;background:rgba(5,7,10,.95);border:2px solid rgba(255,255,255,.16);border-radius:22px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.45)}.top{display:grid;grid-template-columns:1fr 1.25fr 1fr;min-height:170px;background:linear-gradient(90deg,#0b4e83,#111827,#8b1720)}.team{display:flex;align-items:center;gap:18px;padding:22px 28px}.right{justify-content:flex-end;text-align:right}.badge{width:82px;height:82px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:900;background:#eee;color:#111;border:4px solid #fff;flex:none}.team-name{font-size:25px;font-weight:900;text-transform:uppercase}.team-score{font-size:52px;font-weight:900;color:#ffd400}.team-over{font-size:19px;font-weight:800}.center{text-align:center;padding:25px 12px}.status{font-size:23px;font-weight:900;background:#b20f1b;border-radius:14px;padding:12px 16px;display:inline-block}.substatus{margin-top:14px;font-size:19px;color:#ffd400;font-weight:800}.info{display:flex;justify-content:space-around;background:linear-gradient(90deg,#9a121d,#d71920,#9a121d);padding:12px;font-size:20px;font-weight:900}.cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;background:#000}.card{min-height:125px;padding:18px;background:linear-gradient(135deg,#12639a,#183e67);text-align:center}.red{background:linear-gradient(135deg,#a71925,#68131b)}.label{font-size:14px;font-weight:900}.player{font-size:23px;font-weight:900;margin-top:10px}.player-score{font-size:29px;font-weight:900;color:#ffd400;margin-top:5px}.small{font-size:14px;font-weight:800;margin-top:5px}.footer{display:flex;justify-content:space-between;background:#070707;padding:10px 18px;font-size:14px;font-weight:800}@media(max-width:800px){.top{grid-template-columns:1fr 1fr}.center{grid-column:1/3;order:-1}.team{padding:12px}.team-name{font-size:18px}.team-score{font-size:35px}.badge{width:58px;height:58px;font-size:20px}.info{font-size:14px}.player{font-size:18px}}</style></head><body><div id="board"><div class="top"><div class="team"><div class="badge" id="badge1">🏳️</div><div><div class="team-name" id="team1">TEAM 1</div><div class="team-score" id="score1">-</div><div class="team-over" id="over1"></div></div></div><div class="center"><div class="status" id="status">WAITING</div><div class="substatus" id="title">CRICKET</div></div><div class="team right"><div><div class="team-name" id="team2">TEAM 2</div><div class="team-score" id="score2">-</div><div class="team-over" id="over2"></div></div><div class="badge" id="badge2">🏳️</div></div></div><div class="info"><div>CRR: <span id="crr">-</span></div><div>P'SHIP: <span id="partnership">-</span></div><div>LIVE SCORE</div></div><div class="cards"><div class="card"><div class="label">BATTER</div><div class="player" id="bat1">-</div><div class="player-score" id="bat1score">-</div><div class="small" id="bat1stats"></div></div><div class="card"><div class="label">BATTER</div><div class="player" id="bat2">-</div><div class="player-score" id="bat2score">-</div><div class="small" id="bat2stats"></div></div><div class="card red"><div class="label">BOWLER</div><div class="player" id="bowler">-</div><div class="player-score" id="bowlerscore">-</div><div class="small" id="bowlerstats"></div></div></div><div class="footer"><div id="last">UPDATES AUTOMATICALLY</div><div>LIVE CRICKET</div></div></div><script>const MID=%s;const $=id=>document.getElementById(id);const set=(id,v)=>$(id).textContent=v||"-";async function update(){try{const r=await fetch("/selected-score?match_id="+encodeURIComponent(MID)+"&t="+Date.now(),{cache:"no-store"});const d=await r.json();if(!d.selected){set("status","NO MATCH");return}const m=d.match||{};set("team1",(m.team1_flag||"")+" "+(m.team1||"TEAM 1"));set("team2",(m.team2||"TEAM 2")+" "+(m.team2_flag||""));set("score1",m.team1_score);set("score2",m.team2_score);set("over1",m.team1_overs?m.team1_overs+" OVERS":"");set("over2",m.team2_overs?m.team2_overs+" OVERS":"");set("badge1",m.team1_flag||"🏳️");set("badge2",m.team2_flag||"🏳️");set("title",m.title);set("status",m.status);set("crr",m.crr);set("partnership",m.partnership);const b=m.batsmen||[];if(b[0]){set("bat1",b[0].name);set("bat1score",b[0].runs+" ("+b[0].balls+")")}if(b[1]){set("bat2",b[1].name);set("bat2score",b[1].runs+" ("+b[1].balls+")")}if(m.bowler){set("bowler",m.bowler.name);set("bowlerscore",m.bowler.overs+"-"+m.bowler.maidens+"-"+m.bowler.runs+"-"+m.bowler.wickets);set("bowlerstats","ECO: "+m.bowler.economy)}set("last","LAST UPDATE: "+new Date().toLocaleTimeString())}catch(e){set("status","RETRYING DATA");set("last","Live data temporarily unavailable")}}update();setInterval(update,15000);</script></body></html>''' % repr(mid)
    return Response(html,mimetype="text/html")

if __name__=="__main__":
    import os
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
