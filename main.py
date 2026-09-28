from flask import Flask, jsonify, Response, request
import requests
from bs4 import BeautifulSoup
from html import escape
import re

app = Flask(__name__)

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
JINA_PREFIX = "https://r.jina.ai/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

selected_match = None


def clean(value):
    return " ".join(str(value or "").split()).strip()


def absolute_url(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return "https://www.cricbuzz.com" + url


def fetch_matches():
    matches = []
    seen_urls = set()

    def add_match(name, url=""):
        name = clean(name).strip(" -*|#")
        url = absolute_url(url)
        if not name or len(name) < 5 or len(name) > 250:
            return
        key = url or name.lower()
        if key in seen_urls:
            return
        seen_urls.add(key)
        matches.append({
            "id": str(len(matches)),
            "name": name,
            "url": url,
        })

    try:
        response = requests.get(CRICBUZZ_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.select('a[href*="/live-cricket-scores/"]'):
            text = clean(" ".join(link.stripped_strings))
            href = link.get("href", "")
            if text:
                add_match(text, href)

        if matches:
            return matches
    except Exception as error:
        print("Direct Cricbuzz list error:", error)

    try:
        jina_url = JINA_PREFIX + CRICBUZZ_URL
        response = requests.get(jina_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=25)
        response.raise_for_status()
        for line in response.text.splitlines():
            line = clean(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line))
            if re.search(r"\bvs\.?\b", line, re.I):
                add_match(line)
    except Exception as error:
        print("Jina list error:", error)

    return matches


def extract_team_names(title):
    title = clean(title)
    m = re.search(r"(.+?)\s+vs\s+(.+?)(?:,| - |$)", title, re.I)
    if m:
        return clean(m.group(1)), clean(m.group(2))
    return "TEAM 1", "TEAM 2"


def parse_score(text):
    patterns = [
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})\s*-\s*(\d{1,2})\s*\((\d+(?:\.\d+)?)\)",
        r"\b([A-Z][A-Z0-9]{1,6})\s+(\d{1,4})/(\d{1,2})\s*\((\d+(?:\.\d+)?)\)",
    ]
    found = []
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            item = {
                "team_code": m.group(1),
                "runs": int(m.group(2)),
                "wickets": int(m.group(3)),
                "overs": m.group(4),
            }
            if item not in found:
                found.append(item)
    return found


def row_to_player(row):
    values = [clean(x) for x in row.stripped_strings if clean(x)]
    if len(values) < 2:
        return None

    # Cricbuzz scorecard rows normally contain name, R, B, 4s, 6s, SR.
    nums = []
    for value in values[1:]:
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            nums.append(value)

    if not nums:
        return None

    return {
        "name": values[0].replace("*", "").strip(),
        "runs": nums[0] if len(nums) > 0 else "",
        "balls": nums[1] if len(nums) > 1 else "",
        "fours": nums[2] if len(nums) > 2 else "",
        "sixes": nums[3] if len(nums) > 3 else "",
        "strike_rate": nums[4] if len(nums) > 4 else "",
    }


def fetch_match_detail(match):
    url = absolute_url(match.get("url", ""))
    title = match.get("name", "Selected Match")
    team1, team2 = extract_team_names(title)

    result = {
        "title": title,
        "url": url,
        "team1": team1,
        "team2": team2,
        "team1_score": "-",
        "team2_score": "-",
        "team1_overs": "",
        "team2_overs": "",
        "crr": "-",
        "partnership": "-",
        "status": "Waiting for live data",
        "batsmen": [],
        "bowler": None,
        "updated": True,
    }

    if not url:
        return result

    html = ""
    text = ""

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        text = clean(soup.get_text(" ", strip=True))

        h1 = soup.find("h1")
        if h1:
            page_title = clean(h1.get_text(" ", strip=True))
            if page_title:
                result["title"] = page_title.replace(" - Commentary", "").strip()
                team1, team2 = extract_team_names(result["title"])
                result["team1"] = team1
                result["team2"] = team2
    except Exception as error:
        print("Direct match detail error:", error)

    # Jina is a useful fallback because it returns a clean text version of Cricbuzz.
    if not text or len(text) < 300:
        try:
            jina_url = JINA_PREFIX + url
            response = requests.get(jina_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=25)
            response.raise_for_status()
            text = clean(response.text)
        except Exception as error:
            print("Jina match detail error:", error)

    scores = parse_score(text)
    if scores:
        # Current innings is normally the last score shown on the live page.
        current = scores[-1]
        result["team1_score"] = f"{current['runs']}-{current['wickets']}"
        result["team1_overs"] = current["overs"]

        if len(scores) > 1:
            previous = scores[-2]
            result["team2_score"] = f"{previous['runs']}-{previous['wickets']}"
            result["team2_overs"] = previous["overs"]

    m = re.search(r"CRR\s+([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        result["crr"] = m.group(1)

    m = re.search(r"P['’]SHIP\s+([^ ]+\([^)]*\))", text, re.I)
    if m:
        result["partnership"] = m.group(1)

    status_patterns = [
        r"(Match abandoned without toss)",
        r"(Innings Break)",
        r"(Day \d+: Stumps[^.]*?)",
        r"(Match starts[^.]*?)",
        r"(Yet to bat)",
        r"(Live - [^.]+)",
    ]
    for pattern in status_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            result["status"] = clean(m.group(1))
            break
    else:
        if scores:
            result["status"] = "LIVE"

    # Best-effort player extraction from the actual Cricbuzz HTML.
    if html:
        soup = BeautifulSoup(html, "html.parser")
        batter_rows = soup.select(".cb-min-bat-rw")
        for row in batter_rows:
            player = row_to_player(row)
            if player and player["name"].lower() not in {"batter", "bowler"}:
                result["batsmen"].append(player)
            if len(result["batsmen"]) >= 2:
                break

        bowler_rows = soup.select(".cb-min-bowl-rw")
        if bowler_rows:
            result["bowler"] = row_to_player(bowler_rows[0])

    return result


@app.route("/")
def home():
    return jsonify({
        "service": "Cricket Live Score Backend",
        "status": "online",
        "success": True,
    })


@app.route("/live-scores")
def live_scores():
    matches = fetch_matches()
    return jsonify({
        "success": True,
        "count": len(matches),
        "matches": matches,
        "selected_match": selected_match,
    })


@app.route("/select-match", methods=["GET", "POST"])
def select_match():
    global selected_match
    matches = fetch_matches()

    if request.method == "POST":
        match_id = request.form.get("match_id")
        for match in matches:
            if match["id"] == match_id:
                selected_match = match
                break

    cards = ""
    for match in matches:
        cards += f'''<div class="match">
            <div class="live">● LIVE / MATCH</div>
            <div class="name">{escape(match["name"])}</div>
            <form method="POST">
                <input type="hidden" name="match_id" value="{escape(match["id"])}">
                <button type="submit">SELECT THIS MATCH</button>
            </form>
        </div>'''

    if not cards:
        cards = '<div class="empty">No matches found right now.<br><br>Try REFRESH MATCHES.</div>'

    selected_html = ""
    if selected_match:
        selected_html = f'''<div class="selected">
            ✓ SELECTED MATCH<br><br>
            <strong>{escape(selected_match["name"])}</strong><br><br>
            OBS scoreboard URL:<br><br>
            <code>/scoreboard</code>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Select Match</title>
    <style>
    body{{margin:0;background:#101010;color:white;font-family:Arial,sans-serif}}
    .container{{max-width:900px;margin:30px auto;padding:20px}}
    .match{{background:#1d1d1d;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:15px}}
    .live{{color:#00e676;font-size:13px;font-weight:bold;margin-bottom:10px}}
    .name{{font-size:19px;font-weight:bold;margin-bottom:18px}}
    button{{background:#00c853;color:white;border:0;border-radius:7px;padding:12px 20px;font-weight:bold}}
    .refresh{{background:#333;margin-bottom:20px}}
    .selected{{background:#12351f;border:1px solid #00c853;border-radius:10px;padding:20px;margin-bottom:20px}}
    .empty{{background:#1d1d1d;padding:30px;text-align:center;color:#aaa;border-radius:10px}}
    code{{background:#000;padding:5px 8px;border-radius:5px}}
    </style></head><body><div class="container">
    <h1>🏏 CRICKET LIVE SCORE</h1><p>Select today's match for your OBS scoreboard.</p>
    {selected_html}
    <button class="refresh" onclick="location.reload()">↻ REFRESH MATCHES</button>
    {cards}
    </div></body></html>'''
    return Response(html, mimetype="text/html")


@app.route("/selected-match")
def selected():
    return jsonify({"success": True, "match": selected_match})


@app.route("/selected-score")
def selected_score():
    if not selected_match:
        return jsonify({
            "success": True,
            "selected": False,
            "message": "No match selected",
        })

    detail = fetch_match_detail(selected_match)
    return jsonify({
        "success": True,
        "selected": True,
        "match": detail,
    })


@app.route("/scoreboard")
def scoreboard():
    html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OBS Cricket Scoreboard</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;padding:0;width:100%;height:100%;background:transparent!important;overflow:hidden;font-family:Arial,Helvetica,sans-serif;color:#fff}
#board{position:absolute;left:2.5%;right:2.5%;bottom:3%;background:rgba(5,7,10,.94);border:2px solid rgba(255,255,255,.16);border-radius:22px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.45)}
.top{display:grid;grid-template-columns:1fr 1.35fr 1fr;min-height:150px;background:linear-gradient(90deg,#0b4e83,#111827,#8b1720)}
.team{display:flex;align-items:center;gap:18px;padding:22px 30px}
.team.right{justify-content:flex-end;text-align:right}
.badge{width:82px;height:82px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:25px;font-weight:900;background:linear-gradient(145deg,#f4f4f4,#777);color:#111;border:5px solid #fff;flex:none}
.team-name{font-size:26px;font-weight:900;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.team-score{font-size:52px;font-weight:900;line-height:1;color:#ffd400;white-space:nowrap}
.team-over{font-size:22px;color:#fff;margin-top:5px;font-weight:800}
.center{text-align:center;padding:22px 12px}
.status{font-size:25px;font-weight:900;letter-spacing:2px;background:#000;border-radius:14px;padding:12px 18px;display:inline-block}
.status.live{background:#b20f1b}
.substatus{margin-top:14px;font-size:20px;color:#ffd400;font-weight:800}
.info{display:flex;justify-content:space-around;align-items:center;background:linear-gradient(90deg,#9a121d,#d71920,#9a121d);padding:12px 18px;font-size:21px;font-weight:900}
.cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;background:#000}
.card{min-height:125px;padding:18px 22px;background:linear-gradient(135deg,#12639a,#183e67);text-align:center}
.card.red{background:linear-gradient(135deg,#a71925,#68131b)}
.label{font-size:16px;font-weight:900;letter-spacing:1px;margin-bottom:8px}
.player{font-size:25px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.player-score{font-size:31px;font-weight:900;color:#ffd400;margin-top:4px}
.small{font-size:15px;font-weight:800;margin-top:5px}
.footer{display:flex;justify-content:space-between;gap:15px;background:#070707;padding:10px 20px;font-size:16px;font-weight:800;color:#eee}
@media(max-width:900px){.top{grid-template-columns:1fr;}.team,.team.right{justify-content:center;text-align:center}.center{order:-1}.cards{grid-template-columns:1fr}.team-score{font-size:40px}.team-name{font-size:20px}.badge{width:60px;height:60px;font-size:18px}.info{font-size:15px}.footer{font-size:12px}}
</style>
</head>
<body>
<div id="board">
  <div class="top">
    <div class="team">
      <div class="badge" id="badge1">T1</div>
      <div><div class="team-name" id="team1">TEAM 1</div><div class="team-score" id="score1">-</div><div class="team-over" id="over1"></div></div>
    </div>
    <div class="center">
      <div class="status live" id="status">LIVE</div>
      <div class="substatus" id="title">CRICKET</div>
    </div>
    <div class="team right">
      <div><div class="team-name" id="team2">TEAM 2</div><div class="team-score" id="score2">-</div><div class="team-over" id="over2"></div></div>
      <div class="badge" id="badge2">T2</div>
    </div>
  </div>
  <div class="info">
    <div>CRR: <span id="crr">-</span></div>
    <div>P'SHIP: <span id="partnership">-</span></div>
    <div id="sourceStatus">LIVE SCORE</div>
  </div>
  <div class="cards">
    <div class="card"><div class="label">BATTER</div><div class="player" id="bat1">-</div><div class="player-score" id="bat1score">-</div><div class="small" id="bat1stats"></div></div>
    <div class="card"><div class="label">BATTER</div><div class="player" id="bat2">-</div><div class="player-score" id="bat2score">-</div><div class="small" id="bat2stats"></div></div>
    <div class="card red"><div class="label">BOWLER</div><div class="player" id="bowler">-</div><div class="player-score" id="bowlerscore">-</div><div class="small" id="bowlerstats"></div></div>
  </div>
  <div class="footer"><div id="last">SELECT A MATCH TO START</div><div>UPDATES AUTOMATICALLY</div></div>
</div>
<script>
function setText(id,value){document.getElementById(id).textContent=value||'-'}
function initials(name){return (name||'T1').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase()}
function playerScore(p){if(!p)return '-';return (p.runs||'-')+' ('+(p.balls||'-')+')'}
async function updateScore(){
  try{
    const r=await fetch('/selected-score?t='+Date.now(),{cache:'no-store'});
    const d=await r.json();
    if(!d.selected){setText('status','NO MATCH');setText('title','SELECT A MATCH');return}
    const m=d.match||{};
    setText('team1',m.team1);setText('team2',m.team2);
    setText('score1',m.team1_score);setText('score2',m.team2_score);
    setText('over1',m.team1_overs?m.team1_overs+' OVERS':'');setText('over2',m.team2_overs?m.team2_overs+' OVERS':'');
    setText('badge1',initials(m.team1));setText('badge2',initials(m.team2));
    setText('title',m.title);setText('status',m.status||'LIVE');setText('crr',m.crr);setText('partnership',m.partnership);
    const b=m.batsmen||[];
    if(b[0]){setText('bat1',b[0].name);setText('bat1score',playerScore(b[0]));setText('bat1stats','4s: '+(b[0].fours||0)+'  6s: '+(b[0].sixes||0)+'  SR: '+(b[0].strike_rate||'-'))}
    if(b[1]){setText('bat2',b[1].name);setText('bat2score',playerScore(b[1]));setText('bat2stats','4s: '+(b[1].fours||0)+'  6s: '+(b[1].sixes||0)+'  SR: '+(b[1].strike_rate||'-'))}
    if(m.bowler){setText('bowler',m.bowler.name);setText('bowlerscore',(m.bowler.runs||'-')+' R');setText('bowlerstats','Overs: '+(m.bowler.balls||'-')+'  Wkts: '+(m.bowler.fours||'-'))}
    setText('last',m.status||'LIVE SCORE');
  }catch(e){setText('status','SCORE UNAVAILABLE')}
}
updateScore();setInterval(updateScore,10000);
</script>
</body>
</html>'''
    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
