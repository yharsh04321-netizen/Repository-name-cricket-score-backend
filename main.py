from flask import Flask, jsonify, Response, request, redirect
import requests
from bs4 import BeautifulSoup
from html import escape
import re
import time
import json
from urllib.parse import quote, urljoin, quote_plus

app = Flask(__name__)
CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
CACHE_SECONDS = 5
detail_cache = {}
FLAGS = {
    "india":"🇮🇳","west indies":"🌴","australia":"🇦🇺","south africa":"🇿🇦",
    "england":"🏴","sri lanka":"🇱🇰","pakistan":"🇵🇰","hong kong":"🇭🇰",
    "afghanistan":"🇦🇫","bangladesh":"🇧🇩","malaysia":"🇲🇾","nepal":"🇳🇵",
    "zimbabwe":"🇿🇼","new zealand":"🇳🇿","ireland":"🇮🇪","scotland":"🏴",
    "netherlands":"🇳🇱","usa":"🇺🇸","oman":"🇴🇲","canada":"🇨🇦",
    "bermuda":"🇧🇲","cayman islands":"🇰🇾","nigeria":"🇳🇬","sierra leone":"🇸🇱"
}

def clean(v):
    return " ".join(str(v or "").split()).strip()

def absolute_url(url, base="https://www.cricbuzz.com"):
    if not url:
        return ""
    return urljoin(base, url)

def jina_url(url):
    return "https://r.jina.ai/http://" + url.removeprefix("https://").removeprefix("http://")

def team_flag(name):
    low = clean(name).lower()
    for key, flag in FLAGS.items():
        if key in low:
            return flag
    return "🏳️"

def team_code(name):
    n = clean(name).upper()
    codes = {
        "INDIA":"IND","INDIA U19":"INDU19","WEST INDIES":"WI","AUSTRALIA":"AUS","AUSTRALIA U19":"AUSU19",
        "SOUTH AFRICA":"RSA","ENGLAND":"ENG","SRI LANKA":"SL","PAKISTAN":"PAK","HONG KONG":"HK",
        "AFGHANISTAN":"AFG","BANGLADESH":"BAN","MALAYSIA":"MAL","NEPAL":"NEP","ZIMBABWE":"ZIM",
        "NEW ZEALAND":"NZ","IRELAND":"IRE","OMAN":"OMA","USA":"USA","CANADA":"CAN",
        "BERMUDA":"BER","NIGERIA":"NGR","SIERRA LEONE":"SLE","CAYMAN ISLANDS":"CAY"
    }
    return codes.get(n, "".join(x[0] for x in n.split()[:3])[:5] or "T1")

def extract_teams(title):
    title = clean(title)
    m = re.search(r"(.+?)\s+vs\s+(.+?)(?:\s+-\s+|,\s*|$)", title, re.I)
    return (clean(m.group(1)), clean(m.group(2))) if m else ("TEAM 1", "TEAM 2")

def compact_match_name(text, url):
    text = clean(text)
    slug = re.search(r"/live-cricket-scores/\d+/([^/?#]+)", url)
    if slug:
        pair = re.match(r"([a-z0-9]+)-vs-([a-z0-9]+)", slug.group(1), re.I)
        if pair:
            name = f"{pair.group(1).upper()} vs {pair.group(2).upper()}"
            status = re.search(r"(Match abandoned(?: without toss)?|Innings Break|Day\s+\d+\s*:\s*Stumps[^|]*)", text, re.I)
            return name + (" - " + clean(status.group(1)) if status else "")
    return text[:250]

def is_current_card(anchor):
    text = clean(anchor.get_text(" ", strip=True))
    markers = r"match abandoned|abandoned|innings break|day\s+\d+\s*:\s*stumps|won by|match tied|no result|live|\d{1,4}\s*-\s*\d{1,2}\s*\("
    return bool(re.search(markers, text, re.I))

def fetch_matches():
    matches, seen = [], set()
    def add(a):
        url = absolute_url(a.get("href", ""))
        m = re.search(r"/live-cricket-scores/(\d+)", url)
        if not m or not is_current_card(a):
            return
        mid = m.group(1)
        if mid in seen:
            return
        seen.add(mid)
        text = clean(a.get_text(" ", strip=True))
        matches.append({"id": mid, "name": compact_match_name(text, url), "url": url})
    for source in (CRICBUZZ_URL, jina_url(CRICBUZZ_URL)):
        try:
            r = requests.get(source, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select('a[href*="/live-cricket-scores/"]'):
                add(a)
            if matches:
                return matches
        except Exception as e:
            print("match list error:", e)
    return matches

def get_match_by_id(match_id):
    mid = clean(match_id)
    if not mid.isdigit():
        return None
    found = next((m for m in fetch_matches() if str(m["id"]) == mid), None)
    if found:
        return found
    return {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}

def scorecard_url(url):
    if "/live-cricket-scores/" in url:
        return url.replace("/live-cricket-scores/", "/live-cricket-scorecard/", 1)
    return url

def parse_scores(text):
    text = clean(text)
    found = []
    patterns = [
        r"\b([A-Z][A-Z0-9]{1,12})\s+(\d{1,4})\s*-\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)\s*(?:Ov|Overs|over)\b",
        r"\b([A-Z][A-Z0-9]{1,12})\s+(\d{1,4})\s*/\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)\s*\)",
        r"\b([A-Z][A-Z0-9]{1,12})\s+(\d{1,4})\s*-\s*(\d{1,2})\s*\(\s*(\d+(?:\.\d+)?)\s*\)"
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            item = {"code":m.group(1).upper(), "runs":m.group(2), "wickets":m.group(3), "overs":m.group(4)}
            if item not in found:
                found.append(item)
    return found[:4]

def parse_players(text):
    section = clean(text[-18000:])
    bats = []
    patterns = [
        r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,4})\s+(\d+)\s+(\d+)\s+(?:\d+)\s+(?:\d+)\s+(?:[0-9.]+)",
        r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+)\s*\((\d+)\)"
    ]
    for pat in patterns:
        for m in re.finditer(pat, section):
            name = clean(m.group(1)).replace(" *", "")
            if name.lower() in {"over summary", "player of the match", "extras", "total"}:
                continue
            if not any(x["name"] == name for x in bats):
                bats.append({"name":name, "runs":m.group(2), "balls":m.group(3)})
            if len(bats) == 2:
                break
        if len(bats) == 2:
            break
    bowler = None
    m = re.search(r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)", section)
    if m:
        bowler = {"name":clean(m.group(1)).replace(" *", ""), "overs":m.group(2), "maidens":m.group(3), "runs":m.group(4), "wickets":m.group(5), "economy":m.group(6)}
    return bats, bowler

def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", clean(s).lower().replace("(c)", "").replace("(wk)", ""))

def extract_captain_names(text):
    section = clean(text[-30000:])
    found = []
    patterns = [
        r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s*\(c\)",
        r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+captain\b"
    ]
    for pat in patterns:
        for m in re.finditer(pat, section, re.I):
            name = clean(m.group(1)).replace(" *", "")
            if name and len(name.split()) <= 4 and name not in found:
                found.append(name)
            if len(found) >= 2:
                return found[:2]
    return found[:2]

def image_from_profile(profile_url, player_name):
    try:
        r = requests.get(absolute_url(profile_url), headers=HEADERS, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        target = norm_name(player_name)
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
            alt = img.get("alt", "")
            if src and target and target in norm_name(alt):
                return absolute_url(src)
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
            if src and "static.cricbuzz.com" in src:
                return absolute_url(src)
    except Exception as e:
        print("profile image error:", e)
    return ""

def parse_captains(page_html, text):
    names = extract_captain_names(text)
    if not names:
        return []
    soup = BeautifulSoup(page_html or "", "html.parser")
    links = []
    for a in soup.select('a[href*="/profiles/"]'):
        label = clean(a.get_text(" ", strip=True)).replace("(c)", "").strip()
        href = a.get("href", "")
        img = a.find("img")
        src = ""
        if img:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
        links.append((label, href, src))
    result = []
    for name in names:
        image = ""
        profile = ""
        n = norm_name(name)
        for label, href, src in links:
            ln = norm_name(label)
            if ln == n or (n and (n in ln or ln in n)):
                profile = absolute_url(href)
                image = absolute_url(src) if src else ""
                break
        if not image and profile:
            image = image_from_profile(profile, name)
        if not image:
            image = "https://ui-avatars.com/api/?name=" + quote_plus(name) + "&size=256&background=15263c&color=ffffff&bold=true&format=png"
        result.append({"name":name, "image":image})
    return result[:2]

def fetch_match_detail(match):
    match_id = str(match["id"])
    now = time.time()
    cached = detail_cache.get(match_id)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]
    team1, team2 = extract_teams(match.get("name", ""))
    result = {
        "title": match.get("name", "CRICKET"), "url": match.get("url", ""),
        "team1": team1, "team2": team2,
        "team1_code": team_code(team1), "team2_code": team_code(team2),
        "team1_flag": team_flag(team1), "team2_flag": team_flag(team2),
        "team1_score":"-", "team2_score":"-", "team1_overs":"", "team2_overs":"",
        "crr":"-", "partnership":"-", "status":"LIVE DATA TEMPORARILY UNAVAILABLE",
        "batsmen":[], "bowler":None, "captains":[]
    }
    urls = []
    original = match.get("url", "")
    card_url = scorecard_url(original)
    if card_url: urls.append(card_url)
    if original and original not in urls: urls.append(original)
    texts, htmls = [], []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            page_text = clean(soup.get_text(" ", strip=True))
            if soup.title:
                title = clean(soup.title.get_text(" ", strip=True))
                p1, p2 = extract_teams(title)
                if p1 != "TEAM 1":
                    team1, team2 = p1, p2
                    result.update({"title":f"{team1} vs {team2}","team1":team1,"team2":team2,"team1_code":team_code(team1),"team2_code":team_code(team2),"team1_flag":team_flag(team1),"team2_flag":team_flag(team2)})
            texts.append(page_text)
            htmls.append(r.text)
            if len(page_text) > 300:
                break
        except Exception as e:
            print("direct detail error:", e)
    if not texts:
        for url in urls:
            try:
                r = requests.get(jina_url(url), headers={"User-Agent":HEADERS["User-Agent"]}, timeout=15)
                r.raise_for_status()
                texts.append(clean(r.text))
                htmls.append("")
                break
            except Exception as e:
                print("jina detail error:", e)
    text = max(texts, key=len) if texts else ""
    html = htmls[texts.index(text)] if texts and len(htmls) == len(texts) else ""
    scores = parse_scores(text)
    if scores:
        result["team1_score"] = f"{scores[0]['runs']}-{scores[0]['wickets']}"
        result["team1_overs"] = scores[0]["overs"]
    if len(scores) > 1:
        result["team2_score"] = f"{scores[1]['runs']}-{scores[1]['wickets']}"
        result["team2_overs"] = scores[1]["overs"]
    m = re.search(r"\bCRR\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m: result["crr"] = m.group(1)
    m = re.search(r"P['’]?SHIP\s*[: ]\s*([0-9]+(?:\([0-9.]+\))?)", text, re.I)
    if m: result["partnership"] = m.group(1)
    status_patterns = [r"Match abandoned without toss",r"Match abandoned",r"Innings Break",r"Day\s+\d+\s*:\s*Stumps\s*[-:]\s*[^|]{0,120}",r"[A-Za-z ]+ won by \d+ runs",r"[A-Za-z ]+ won by \d+ wickets"]
    for pat in status_patterns:
        m = re.search(pat, text, re.I)
        if m:
            result["status"] = clean(m.group(0)); break
    else:
        if scores: result["status"] = "LIVE"
    result["batsmen"], result["bowler"] = parse_players(text)
    result["captains"] = parse_captains(html, text)
    detail_cache[match_id] = {"time":now, "data":result}
    return result

@app.route("/")
def home():
    return jsonify({"service":"Cricket Live Score Backend","status":"online","success":True})

@app.route("/live-scores")
def live_scores():
    matches = fetch_matches()
    return jsonify({"success":True,"count":len(matches),"matches":matches})

@app.route("/select-match", methods=["GET","POST"])
def select_match():
    matches = fetch_matches()
    if request.method == "POST":
        mid = request.form.get("match_id", "")
        if any(str(m["id"]) == str(mid) for m in matches):
            return redirect("/select-match?selected=" + quote(str(mid)))
    selected_id = request.args.get("selected", "")
    selected = next((m for m in matches if str(m["id"]) == str(selected_id)), None)
    cards = "".join(f'''<div class="match"><div class="live">● TODAY / LIVE</div><div class="name">{escape(m["name"])}</div><form method="POST"><input type="hidden" name="match_id" value="{escape(m["id"])}"><button>SELECT THIS MATCH</button></form></div>''' for m in matches)
    if not cards: cards = '<div class="empty">No current matches found right now.</div>'
    selected_html = ""
    if selected:
        board = "/scoreboard?match_id=" + quote(str(selected["id"]))
        selected_html = f'''<div class="selected">✓ SELECTED MATCH<br><br><strong>{escape(selected["name"])}</strong><br><br>OBS scoreboard URL:<br><br><code>{escape(board)}</code><br><br><a href="{escape(board)}">OPEN SCOREBOARD</a></div>'''
    html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Select Match</title><style>body{{margin:0;background:#101010;color:#fff;font-family:Arial}}.container{{max-width:900px;margin:30px auto;padding:20px}}.match{{background:#1d1d1d;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:15px}}.live{{color:#00e676;font-size:13px;font-weight:bold;margin-bottom:10px}}.name{{font-size:19px;font-weight:bold;margin-bottom:18px}}button,a{{background:#00c853;color:#fff;border:0;border-radius:7px;padding:12px 20px;font-weight:bold;text-decoration:none;display:inline-block}}.refresh{{background:#333;margin-bottom:20px}}.selected{{background:#12351f;border:1px solid #00c853;border-radius:10px;padding:20px;margin-bottom:20px}}.empty{{background:#1d1d1d;padding:30px;text-align:center;color:#aaa;border-radius:10px}}code{{background:#000;padding:5px 8px;border-radius:5px}}</style></head><body><div class="container"><h1>🏏 CRICKET LIVE SCORE</h1><p>Today's current cricket matches for your OBS scoreboard.</p>{selected_html}<button class="refresh" onclick="location.href='/select-match'">↻ REFRESH MATCHES</button>{cards}</div></body></html>'''
    return Response(html, mimetype="text/html")

@app.route("/selected-match")
def selected_match_api():
    mid = request.args.get("match_id", "")
    m = get_match_by_id(mid) if mid else None
    return jsonify({"success":True,"selected":bool(m),"match":m})

@app.route("/selected-score")
def selected_score():
    mid = request.args.get("match_id", "")
    m = get_match_by_id(mid) if mid else None
    if not m:
        return jsonify({"success":True,"selected":False,"message":"No match selected"})
    try:
        data = fetch_match_detail(m)
        return jsonify({"success":True,"selected":True,"match":data})
    except Exception as e:
        print("selected score error:", repr(e))
        t1, t2 = extract_teams(m.get("name", ""))
        fallback = {"title":m.get("name","CRICKET"),"team1":t1,"team2":t2,"team1_code":team_code(t1),"team2_code":team_code(t2),"team1_flag":team_flag(t1),"team2_flag":team_flag(t2),"team1_score":"-","team2_score":"-","team1_overs":"","team2_overs":"","crr":"-","partnership":"-","status":"DATA RETRYING","batsmen":[],"bowler":None,"captains":[]}
        return jsonify({"success":True,"selected":True,"match":fallback})

@app.route("/scoreboard")
def scoreboard():
    mid = request.args.get("match_id", "")
    if not mid:
        return Response("<html><body style='font-family:Arial;padding:30px'>Select a match first. Open <a href='/select-match'>Match Selector</a>.</body></html>", mimetype="text/html")
    mid_js = json.dumps(str(mid))
    html = '''<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OBS Cricket Scoreboard</title><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:transparent!important;overflow:hidden;font-family:Arial,Helvetica,sans-serif;color:#fff}.wrap{width:100vw;height:100vh;padding:1.2vw;background:transparent}.board{width:100%;height:100%;display:flex;flex-direction:column;overflow:hidden;border-radius:18px;background:#07111f;box-shadow:0 0 35px rgba(0,0,0,.55);border:2px solid rgba(255,255,255,.12)}.hero{flex:0 0 47%;display:grid;grid-template-columns:1fr 1.45fr 1fr;background:linear-gradient(110deg,#062d54 0%,#081426 46%,#280913 100%)}.side{padding:2vw;display:flex;align-items:center;gap:1.2vw}.side.right{justify-content:flex-end;text-align:right}.flag{width:6vw;height:6vw;min-width:58px;min-height:58px;border-radius:50%;background:#f4f4f4;color:#111;display:flex;align-items:center;justify-content:center;font-size:2.5vw;border:3px solid #fff;box-shadow:0 0 18px rgba(255,255,255,.2)}.team{font-size:2.15vw;font-weight:1000;letter-spacing:.04em;text-transform:uppercase}.score{font-size:5vw;line-height:1;color:#ffd21a;font-weight:1000;margin-top:.25vw}.overs{font-size:1.2vw;font-weight:800;margin-top:.4vw;color:#e7edf5}.middle{margin:1vw .5vw;padding:.7vw 1vw;border-radius:14px;background:linear-gradient(145deg,#a80e1d,#ef1e35 52%,#9f0d1c);border:2px solid rgba(255,255,255,.18);box-shadow:0 0 24px rgba(230,20,45,.28),inset 0 0 24px rgba(255,255,255,.07);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;overflow:hidden}.battle{font-size:1.45vw;font-weight:1000;letter-spacing:.04em;font-style:italic;margin-bottom:.05vw;text-shadow:0 2px 5px rgba(0,0,0,.4)}.versus{font-size:1.8vw;font-weight:1000;color:#fff;line-height:1;margin:.1vw 0}.captains{display:flex;align-items:center;justify-content:center;gap:.45vw;width:100%;height:9vw}.captain{width:44%;height:8.1vw;padding:.3vw;border-radius:12px;background:linear-gradient(180deg,rgba(5,37,72,.9),rgba(4,21,39,.85));border:1px solid rgba(90,190,255,.75);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;animation:fighterFloat 2.4s ease-in-out infinite}.captain.redcap{background:linear-gradient(180deg,rgba(90,7,20,.9),rgba(46,3,10,.88));border-color:rgba(255,185,195,.75);animation-delay:.35s}.capphoto{width:4.9vw;height:4.9vw;min-width:52px;min-height:52px;border-radius:50%;object-fit:cover;background:#18283c;border:2px solid #fff;display:block;animation:captainPulse 2s ease-in-out infinite}.captext{width:100%;overflow:hidden}.caprole{font-size:.55vw;color:#ffe15a;font-weight:900;text-transform:uppercase}.capname{font-size:.8vw;font-weight:1000;line-height:1.05;margin-top:.08vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.capteam{font-size:.55vw;color:#f3d8dc;margin-top:.1vw;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.vs-badge{flex:0 0 auto;width:2.2vw;height:2.2vw;min-width:27px;min-height:27px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#ffd21a;color:#4d0710;font-size:.72vw;font-weight:1000;border:2px solid #fff;box-shadow:0 0 14px rgba(255,210,26,.55);animation:vsPulse 1.6s ease-in-out infinite}.status{margin-top:.2vw;padding:.3vw .7vw;border-radius:999px;background:rgba(80,0,8,.62);border:1px solid rgba(255,255,255,.25);font-size:.58vw;font-weight:1000;letter-spacing:.03em;max-width:95%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.info{flex:0 0 9%;display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;text-align:center;background:linear-gradient(90deg,#b10f1e,#e21b2e,#b10f1e);font-size:1.25vw;font-weight:1000}.info b{color:#ffe15a}.cards{flex:1;display:grid;grid-template-columns:1.25fr 1.25fr 1fr;gap:3px;background:#02050a;min-height:0}.card{padding:1.2vw 1.5vw;background:linear-gradient(135deg,#07518b,#0a3158);display:flex;flex-direction:column;justify-content:center}.card.red{background:linear-gradient(135deg,#8e1524,#4d0b15)}.label{font-size:.9vw;font-weight:1000;letter-spacing:.08em;color:#c9d6e6;border-bottom:1px solid rgba(255,255,255,.2);padding-bottom:.45vw}.pname{font-size:1.55vw;font-weight:1000;margin-top:.65vw}.pstat{font-size:1.9vw;font-weight:1000;color:#ffd21a;margin-top:.2vw}.sub{font-size:.82vw;color:#d4dde8;font-weight:800;margin-top:.25vw}.footer{flex:0 0 6%;display:flex;align-items:center;justify-content:space-between;padding:0 1.5vw;background:#02050a;font-size:.8vw;font-weight:900;letter-spacing:.05em}.live{color:#ffdf4a}.dot{display:inline-block;width:.65vw;height:.65vw;background:#22e56f;border-radius:50%;margin-right:.35vw;box-shadow:0 0 10px #22e56f}@keyframes fighterFloat{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-3px) scale(1.025)}}@keyframes captainPulse{0%,100%{transform:scale(1);box-shadow:0 0 0 rgba(255,255,255,0)}50%{transform:scale(1.06);box-shadow:0 0 18px rgba(255,255,255,.3)}}@keyframes vsPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}@media(max-width:900px){.wrap{padding:0}.board{border-radius:0}.team{font-size:3vw}.score{font-size:7vw}.overs{font-size:1.8vw}.middle{margin:.6vw .25vw;padding:.5vw}.battle{font-size:2.4vw}.versus{font-size:3vw}.captains{height:11vw}.captain{height:10vw}.capphoto{width:6.2vw;height:6.2vw}.caprole{font-size:.9vw}.capname{font-size:1.25vw}.capteam{font-size:.9vw}.vs-badge{font-size:1vw}.status{font-size:1vw}.info{font-size:1.8vw}.pname{font-size:2.3vw}.pstat{font-size:2.8vw}.label{font-size:1.3vw}.sub{font-size:1.1vw}}
</style></head><body><div class="wrap"><div class="board"><div class="hero"><div class="side"><div class="flag" id="flag1">🏳️</div><div><div class="team" id="team1">TEAM 1</div><div class="score" id="score1">-</div><div class="overs" id="over1"></div></div></div><div class="middle"><div class="battle">CAPTAINS BATTLE</div><div class="captains"><div class="captain" id="capcard1"><img class="capphoto" id="capimg1" alt="Captain 1"><div class="captext"><div class="caprole">CAPTAIN</div><div class="capname" id="cap1">-</div><div class="capteam" id="cap1team">TEAM 1</div></div></div><div class="vs-badge">VS</div><div class="captain redcap" id="capcard2"><img class="capphoto" id="capimg2" alt="Captain 2"><div class="captext"><div class="caprole">CAPTAIN</div><div class="capname" id="cap2">-</div><div class="capteam" id="cap2team">TEAM 2</div></div></div></div><div class="status" id="status">WAITING FOR LIVE DATA</div></div><div class="side right"><div><div class="team" id="team2">TEAM 2</div><div class="score" id="score2">-</div><div class="overs" id="over2"></div></div><div class="flag" id="flag2">🏳️</div></div></div><div class="info"><div>CRR <b id="crr">-</b></div><div>P'SHIP <b id="partnership">-</b></div><div id="matchtitle">LIVE CRICKET</div></div><div class="cards"><div class="card"><div class="label">BATTER 1</div><div class="pname" id="bat1">-</div><div class="pstat" id="bat1score">-</div><div class="sub" id="bat1stats">LIVE BATTER</div></div><div class="card"><div class="label">BATTER 2</div><div class="pname" id="bat2">-</div><div class="pstat" id="bat2score">-</div><div class="sub" id="bat2stats">LIVE BATTER</div></div><div class="card red"><div class="label">BOWLER</div><div class="pname" id="bowler">-</div><div class="pstat" id="bowlerscore">-</div><div class="sub" id="bowlerstats">LIVE BOWLER</div></div></div><div class="footer"><div id="last">UPDATES AUTOMATICALLY</div><div class="live"><span class="dot"></span>LIVE CRICKET</div></div></div></div><script>
const MID=__MID__;const $=id=>document.getElementById(id);const set=(id,v)=>$(id).textContent=(v===undefined||v===null||v==="")?"-":v;
function cartoonAvatar(name, side){const safe=(name||"Captain").replace(/[^a-zA-Z0-9 ]/g,"");const initial=(safe.trim()[0]||"C").toUpperCase();const bg=side===1?"#0b69b5":"#9d1427";const shirt=side===1?"#0877c9":"#c61e35";const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${bg}"/><stop offset="1" stop-color="#07111f"/></linearGradient></defs><rect width="220" height="220" rx="110" fill="url(#g)"/><circle cx="110" cy="87" r="43" fill="#f2c29b"/><path d="M68 79c6-43 78-52 88 2-23-16-59-12-88-2z" fill="#1d1d1d"/><path d="M61 57h98l-12 18H72z" fill="#101820"/><circle cx="95" cy="90" r="4"/><circle cx="125" cy="90" r="4"/><path d="M96 108q14 10 28 0" fill="none" stroke="#7a3d2b" stroke-width="4" stroke-linecap="round"/><path d="M64 152q46-38 92 0l18 68H46z" fill="${shirt}"/><path d="M79 150l31 34 31-34" fill="#fff" opacity=".9"/><circle cx="110" cy="184" r="18" fill="#ffd21a"/><text x="110" y="192" text-anchor="middle" font-family="Arial" font-size="24" font-weight="900" fill="#4a0710">${initial}</text></svg>`;return "data:image/svg+xml;charset=UTF-8,"+encodeURIComponent(svg)}
function captain(img,name,team,data,side){const n=(data&&data.name)||"Captain";set(name,n);set(team,team==="cap1team"?($("team1").textContent||"TEAM 1"):($("team2").textContent||"TEAM 2"));const el=$(img);el.onerror=()=>{el.src=cartoonAvatar(n,side)};el.style.display="block";el.src=cartoonAvatar(n,side)}
async function update(){try{const r=await fetch("/selected-score?match_id="+encodeURIComponent(MID)+"&t="+Date.now(),{cache:"no-store"});const d=await r.json();if(!d.selected){set("status","NO MATCH");return}const m=d.match||{};set("team1",m.team1||"TEAM 1");set("team2",m.team2||"TEAM 2");set("score1",m.team1_score);set("score2",m.team2_score);set("over1",m.team1_overs?m.team1_overs+" OVERS":"");set("over2",m.team2_overs?m.team2_overs+" OVERS":"");set("flag1",m.team1_flag||"🏳️");set("flag2",m.team2_flag||"🏳️");set("cap1team",m.team1||"TEAM 1");set("cap2team",m.team2||"TEAM 2");const caps=m.captains||[];captain("capimg1","cap1","cap1team",caps[0],1);captain("capimg2","cap2","cap2team",caps[1],2);set("status",m.status||"LIVE");set("crr",m.crr);set("partnership",m.partnership);set("matchtitle",m.title||"LIVE CRICKET");const b=m.batsmen||[];if(b[0]){set("bat1",b[0].name);set("bat1score",b[0].runs+" ("+b[0].balls+")")}else{set("bat1","-");set("bat1score","-")}if(b[1]){set("bat2",b[1].name);set("bat2score",b[1].runs+" ("+b[1].balls+")")}else{set("bat2","-");set("bat2score","-")}if(m.bowler){set("bowler",m.bowler.name);set("bowlerscore",m.bowler.overs+"-"+m.bowler.maidens+"-"+m.bowler.runs+"-"+m.bowler.wickets);set("bowlerstats","ECO: "+m.bowler.economy)}else{set("bowler","-");set("bowlerscore","-");set("bowlerstats","LIVE BOWLER")}set("last","LAST UPDATE: "+new Date().toLocaleTimeString())}catch(e){set("status","RETRYING LIVE DATA");set("last","Live data temporarily unavailable")}}update();setInterval(update,15000);
</script></body></html>'''.replace("__MID__", mid_js)
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
