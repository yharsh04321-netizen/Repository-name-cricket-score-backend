from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
from html import escape
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
selected_match = None


def clean(value):
    return " ".join(str(value or "").split()).strip()


def absolute_url(url):
    if not url:
        return ""
    return url if url.startswith("http") else "https://www.cricbuzz.com" + url


def jina_url(url):
    return "https://r.jina.ai/http://" + url.removeprefix("https://").removeprefix("http://")


def fetch_matches():
    matches, seen = [], set()

    def add(name, url=""):
        name = clean(name).strip(" -*|#")
        url = absolute_url(url)
        if len(name) < 5 or len(name) > 250:
            return
        key = url or name.lower()
        if key in seen:
            return
        seen.add(key)
        matches.append({"id": str(len(matches)), "name": name, "url": url})

    for source in (CRICBUZZ_URL, jina_url(CRICBUZZ_URL)):
        try:
            r = requests.get(source, headers=HEADERS, timeout=25)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select('a[href*="/live-cricket-scores/"]'):
                add(" ".join(a.stripped_strings), a.get("href", ""))
            if matches:
                return matches
        except Exception as e:
            print("match list error:", e)
    return matches


def extract_team_names(title):
    title = clean(title)
    m = re.search(r"(.+?)\s+vs\s+(.+?)(?:,|\s+-\s+|$)", title, re.I)
    return (clean(m.group(1)), clean(m.group(2))) if m else ("TEAM 1", "TEAM 2")


def parse_scores(text):
    head = text[:5000]
    patterns = [
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*/\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)\s*(?:Ov|Overs)?\s*\)",
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*-\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)\s*(?:Ov|Overs)?\s*\)",
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*\(\s*(\d+(?:\.\d+)?)\s*(?:Ov|Overs)?\s*\)",
    ]
    found = []
    for pattern in patterns:
        for m in re.finditer(pattern, head):
            if len(m.groups()) == 4:
                wickets = int(m.group(3))
                overs = m.group(4)
            else:
                wickets = 0
                overs = m.group(3)
            item = {"team_code": m.group(1), "runs": int(m.group(2)), "wickets": wickets, "overs": overs}
            if item not in found:
                found.append(item)
    return found


def parse_players(text):
    blocks = list(re.finditer(r"Over\s+\d+", text, re.I))
    section = text[blocks[-1].start():] if blocks else text

    players = []
    for m in re.finditer(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+)\s*\((\d+)\)", section):
        name, runs, balls = m.group(1).strip(), m.group(2), m.group(3)
        if name.lower() in {"over summary", "player of the match", "south africa", "australia"}:
            continue
        if not any(p["name"] == name for p in players):
            players.append({"name": name, "runs": runs, "balls": balls, "fours": "", "sixes": "", "strike_rate": ""})
        if len(players) >= 2:
            break

    bowler = None
    for m in re.finditer(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)-(\d+)-(\d+)-(\d+(?:\.\d+)?)\b", section):
        bowler = {"name": m.group(1).strip(), "overs": m.group(2), "maidens": m.group(3), "runs": m.group(4), "wickets": m.group(5), "economy": m.group(6)}
        break
    return players, bowler


def fetch_match_detail(match):
    url = absolute_url(match.get("url", ""))
    result = {
        "title": match.get("name", "Selected Match"), "url": url,
        "team1": "TEAM 1", "team2": "TEAM 2",
        "team1_code": "T1", "team2_code": "T2",
        "team1_score": "-", "team2_score": "-",
        "team1_overs": "", "team2_overs": "",
        "crr": "-", "partnership": "-", "status": "Waiting for live data",
        "batsmen": [], "bowler": None,
    }
    result["team1"], result["team2"] = extract_team_names(result["title"])
    result["team1_code"] = result["team1"].upper()[:6]
    result["team2_code"] = result["team2"].upper()[:6]
    if not url:
        return result

    direct_text = ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        direct_text = soup.get_text(" ", strip=True)
        h1 = soup.find("h1")
        if h1:
            title = clean(h1.get_text(" ", strip=True)).replace(" - Commentary", "").replace(" - Scorecard", "")
            if title:
                result["title"] = title
                result["team1"], result["team2"] = extract_team_names(title)
    except Exception as e:
        print("direct detail error:", e)

    text = direct_text
    if not re.search(r"\b[A-Z]{2,6}\s+\d{1,4}(?:/|-)?\d*\s*\(", text[:8000]):
        try:
            r = requests.get(jina_url(url), headers={"User-Agent": HEADERS["User-Agent"]}, timeout=25)
            r.raise_for_status()
            text = r.text
        except Exception as e:
            print("Jina detail error:", e)

    text = clean(text)
    scores = parse_scores(text)
    by_code = {s["team_code"]: s for s in scores}

    for code, score in by_code.items():
        if code in {"RSA", "SA"} and result["team1_code"] in {"SOUTH", "RSA"}:
            result["team1_score"] = f"{score['runs']}-{score['wickets']}"
            result["team1_overs"] = score["overs"]
        elif code == "AUS" and result["team2_code"] in {"AUSTRA", "AUS"}:
            result["team2_score"] = f"{score['runs']}-{score['wickets']}"
            result["team2_overs"] = score["overs"]
        elif code in {"IND", "INDIA"} and result["team1_code"] in {"INDIA", "IND"}:
            result["team1_score"] = f"{score['runs']}-{score['wickets']}"
            result["team1_overs"] = score["overs"]
        elif code in {"WI", "WIW", "WI"} and result["team1_code"].startswith("WEST"):
            result["team1_score"] = f"{score['runs']}-{score['wickets']}"
            result["team1_overs"] = score["overs"]

    if result["team1_score"] == "-" and scores:
        s = scores[0]
        result["team1_score"] = f"{s['runs']}-{s['wickets']}"
        result["team1_overs"] = s["overs"]
    if result["team2_score"] == "-" and len(scores) > 1:
        s = scores[1]
        result["team2_score"] = f"{s['runs']}-{s['wickets']}"
        result["team2_overs"] = s["overs"]

    m = re.search(r"\bCRR\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        result["crr"] = m.group(1)
    m = re.search(r"P['’]?SHIP\s*[: ]\s*([0-9]+(?:\([0-9.]+\))?)", text, re.I)
    if m:
        result["partnership"] = m.group(1)

    for pat in [r"(Match abandoned without toss)", r"([A-Za-z ]+ won by \d+ runs)", r"(Innings Break)", r"(Day \d+: Stumps[^.]*?)"]:
        m = re.search(pat, text, re.I)
        if m:
            result["status"] = clean(m.group(1))
            break
    else:
        if scores:
            result["status"] = "LIVE"

    result["batsmen"], result["bowler"] = parse_players(text)
    return result


@app.route("/")
def home():
    return jsonify({"service":"Cricket Live Score Backend","status":"online","success":True})


@app.route("/live-scores")
def live_scores():
    matches = fetch_matches()
    return jsonify({"success":True,"count":len(matches),"matches":matches,"selected_match":selected_match})


@app.route("/select-match", methods=["GET","POST"])
def select_match():
    global selected_match
    matches = fetch_matches()
    if request.method == "POST":
        mid = request.form.get("match_id")
        selected_match = next((m for m in matches if m["id"] == mid), selected_match)
    cards = "".join(f'''<div class="match"><div class="live">● LIVE / MATCH</div><div class="name">{escape(m["name"])}</div><form method="POST"><input type="hidden" name="match_id" value="{escape(m["id"])}"><button>SELECT THIS MATCH</button></form></div>''' for m in matches)
    if not cards:
        cards = '<div class="empty">No matches found right now.<br><br>Try REFRESH MATCHES.</div>'
    selected_html = f'''<div class="selected">✓ SELECTED MATCH<br><br><strong>{escape(selected_match["name"])}</strong><br><br>OBS scoreboard URL:<br><br><code>/scoreboard</code></div>''' if selected_match else ""
    html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Select Match</title><style>body{{margin:0;background:#101010;color:white;font-family:Arial}}.container{{max-width:900px;margin:30px auto;padding:20px}}.match{{background:#1d1d1d;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:15px}}.live{{color:#00e676;font-size:13px;font-weight:bold;margin-bottom:10px}}.name{{font-size:19px;font-weight:bold;margin-bottom:18px}}button{{background:#00c853;color:white;border:0;border-radius:7px;padding:12px 20px;font-weight:bold}}.refresh{{background:#333;margin-bottom:20px}}.selected{{background:#12351f;border:1px solid #00c853;border-radius:10px;padding:20px;margin-bottom:20px}}.empty{{background:#1d1d1d;padding:30px;text-align:center;color:#aaa;border-radius:10px}}code{{background:#000;padding:5px 8px;border-radius:5px}}</style></head><body><div class="container"><h1>🏏 CRICKET LIVE SCORE</h1><p>Select today's match for your OBS scoreboard.</p>{selected_html}<button class="refresh" onclick="location.reload()">↻ REFRESH MATCHES</button>{cards}</div></body></html>'''
    return Response(html,mimetype="text/html")


@app.route("/selected-match")
def selected():
    return jsonify({"success":True,"match":selected_match})


@app.route("/selected-score")
def selected_score():
    if not selected_match:
        return jsonify({"success":True,"selected":False,"message":"No match selected"})
    return jsonify({"success":True,"selected":True,"match":fetch_match_detail(selected_match)})


@app.route("/scoreboard")
def scoreboard():
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OBS Cricket Scoreboard</title><style>*{box-sizing:border-box}html,body{margin:0;padding:0;width:100%;height:100%;background:transparent!important;overflow:hidden;font-family:Arial;color:#fff}#board{position:absolute;left:2.5%;right:2.5%;bottom:3%;background:rgba(5,7,10,.94);border:2px solid rgba(255,255,255,.16);border-radius:22px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.45)}.top{display:grid;grid-template-columns:1fr 1.35fr 1fr;min-height:150px;background:linear-gradient(90deg,#0b4e83,#111827,#8b1720)}.team{display:flex;align-items:center;gap:18px;padding:22px 30px}.right{justify-content:flex-end;text-align:right}.badge{width:82px;height:82px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:25px;font-weight:900;background:linear-gradient(145deg,#f4f4f4,#777);color:#111;border:5px solid #fff;flex:none}.team-name{font-size:26px;font-weight:900;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.team-score{font-size:52px;font-weight:900;color:#ffd400}.team-over{font-size:22px;margin-top:5px;font-weight:800}.center{text-align:center;padding:22px 12px}.status{font-size:25px;font-weight:900;letter-spacing:2px;background:#000;border-radius:14px;padding:12px 18px;display:inline-block}.status.live{background:#b20f1b}.substatus{margin-top:14px;font-size:20px;color:#ffd400;font-weight:800}.info{display:flex;justify-content:space-around;background:linear-gradient(90deg,#9a121d,#d71920,#9a121d);padding:12px 18px;font-size:21px;font-weight:900}.cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;background:#000}.card{min-height:125px;padding:18px 22px;background:linear-gradient(135deg,#12639a,#183e67);text-align:center}.red{background:linear-gradient(135deg,#a71925,#68131b)!important}.label{font-size:16px;font-weight:900;margin-bottom:8px}.player{font-size:25px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.player-score{font-size:31px;font-weight:900;color:#ffd400;margin-top:4px}.small{font-size:15px;font-weight:800;margin-top:5px}.footer{display:flex;justify-content:space-between;background:#070707;padding:10px 20px;font-size:16px;font-weight:800}@media(max-width:900px){.top{grid-template-columns:1fr}.team,.right{justify-content:center;text-align:center}.center{order:-1}.cards{grid-template-columns:1fr}.team-score{font-size:40px}.team-name{font-size:20px}.badge{width:60px;height:60px;font-size:18px}.info{font-size:15px}.footer{font-size:12px}}</style></head><body><div id="board"><div class="top"><div class="team"><div class="badge" id="badge1">T1</div><div><div class="team-name" id="team1">TEAM 1</div><div class="team-score" id="score1">-</div><div class="team-over" id="over1"></div></div></div><div class="center"><div class="status live" id="status">LIVE</div><div class="substatus" id="title">CRICKET</div></div><div class="team right"><div><div class="team-name" id="team2">TEAM 2</div><div class="team-score" id="score2">-</div><div class="team-over" id="over2"></div></div><div class="badge" id="badge2">T2</div></div></div><div class="info"><div>CRR: <span id="crr">-</span></div><div>P'SHIP: <span id="partnership">-</span></div><div>LIVE SCORE</div></div><div class="cards"><div class="card"><div class="label">BATTER</div><div class="player" id="bat1">-</div><div class="player-score" id="bat1score">-</div><div class="small" id="bat1stats"></div></div><div class="card"><div class="label">BATTER</div><div class="player" id="bat2">-</div><div class="player-score" id="bat2score">-</div><div class="small" id="bat2stats"></div></div><div class="card red"><div class="label">BOWLER</div><div class="player" id="bowler">-</div><div class="player-score" id="bowlerscore">-</div><div class="small" id="bowlerstats"></div></div></div><div class="footer"><div id="last">SELECT A MATCH TO START</div><div>UPDATES AUTOMATICALLY</div></div></div><script>const $=id=>document.getElementById(id);function set(id,v){$(id).textContent=v||'-'}function ini(n){return(n||'T1').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase()}async function update(){try{const r=await fetch('/selected-score?t='+Date.now(),{cache:'no-store'}),d=await r.json();if(!d.selected){set('status','NO MATCH');set('title','SELECT A MATCH');return}const m=d.match||{};set('team1',m.team1);set('team2',m.team2);set('score1',m.team1_score);set('score2',m.team2_score);set('over1',m.team1_overs?m.team1_overs+' OVERS':'');set('over2',m.team2_overs?m.team2_overs+' OVERS':'');set('badge1',ini(m.team1));set('badge2',ini(m.team2));set('title',m.title);set('status',m.status);set('crr',m.crr);set('partnership',m.partnership);const b=m.batsmen||[];if(b[0]){set('bat1',b[0].name);set('bat1score',b[0].runs+' ('+b[0].balls+')');set('bat1stats','4s: '+(b[0].fours||'-')+'  6s: '+(b[0].sixes||'-')+'  SR: '+(b[0].strike_rate||'-'))}if(b[1]){set('bat2',b[1].name);set('bat2score',b[1].runs+' ('+b[1].balls+')');set('bat2stats','4s: '+(b[1].fours||'-')+'  6s: '+(b[1].sixes||'-')+'  SR: '+(b[1].strike_rate||'-'))}if(m.bowler){set('bowler',m.bowler.name);set('bowlerscore',m.bowler.overs+'-'+m.bowler.maidens+'-'+m.bowler.runs+'-'+m.bowler.wickets);set('bowlerstats','ECO: '+m.bowler.economy)}set('last',m.status)}catch(e){set('status','SCORE UNAVAILABLE')}}update();setInterval(update,10000)</script></body></html>'''
    return Response(html,mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0",port=10000)
