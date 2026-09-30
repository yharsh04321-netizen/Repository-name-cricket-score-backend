from flask import Response, request, redirect
from html import escape
from urllib.parse import quote
import livefix
import main

app = livefix.app

UPCOMING = [
    ("upcoming-ind-wi-3odi", "India 🇮🇳 vs West Indies 🌴 — 3rd ODI", "03 Oct 2026", "2:00 PM IST", "PCA International Cricket Stadium, New Chandigarh"),
    ("upcoming-ind-wi-1t20", "India 🇮🇳 vs West Indies 🌴 — 1st T20I", "06 Oct 2026", "7:00 PM IST", "Ekana Cricket Stadium, Lucknow"),
    ("upcoming-ind-wi-2t20", "India 🇮🇳 vs West Indies 🌴 — 2nd T20I", "09 Oct 2026", "7:00 PM IST", "JSCA International Stadium, Ranchi"),
    ("upcoming-ind-wi-3t20", "India 🇮🇳 vs West Indies 🌴 — 3rd T20I", "11 Oct 2026", "7:00 PM IST", "Holkar Stadium, Indore"),
    ("upcoming-ind-wi-4t20", "India 🇮🇳 vs West Indies 🌴 — 4th T20I", "14 Oct 2026", "7:00 PM IST", "Rajiv Gandhi International Stadium, Hyderabad"),
    ("upcoming-ind-wi-5t20", "India 🇮🇳 vs West Indies 🌴 — 5th T20I", "17 Oct 2026", "7:00 PM IST", "M Chinnaswamy Stadium, Bengaluru"),
]


def selector():
    # Live lookup is optional; upcoming cards must still render if the live source is unavailable.
    try:
        live_matches = main.fetch_matches()
    except Exception as e:
        print("selector live lookup error:", repr(e))
        live_matches = []

    selected = request.args.get("selected", "")
    if request.method == "POST":
        mid = request.form.get("match_id", "")
        if mid.startswith("upcoming-"):
            return redirect("/select-match?selected=" + quote(mid))
        if any(str(m.get("id")) == str(mid) for m in live_matches):
            return redirect("/select-match?selected=" + quote(mid))

    live_html = "".join(
        f'''<div class="card livecard"><div class="live">● LIVE / TODAY</div><div class="title">{escape(str(m.get("name","Match")))}</div><form method="POST"><input type="hidden" name="match_id" value="{escape(str(m.get("id","")))}"><button>SELECT THIS MATCH</button></form></div>'''
        for m in live_matches
    ) or '<div class="empty">No live matches found right now.</div>'

    upcoming_html = "".join(
        f'''<div class="card upcoming"><div class="up">🕒 UPCOMING</div><div class="title">{escape(name)}</div><div class="date">{date} · {time}</div><div class="venue">{escape(venue)}</div><form method="POST"><input type="hidden" name="match_id" value="{mid}"><button class="blue">SELECT UPCOMING MATCH</button></form></div>'''
        for mid, name, date, time, venue in UPCOMING
    )

    selected_html = ""
    match = next((x for x in UPCOMING if x[0] == selected), None)
    if match:
        board = "/scoreboard?match_id=" + quote(match[0])
        selected_html = f'''<div class="selected"><b>✓ UPCOMING MATCH SELECTED</b><br>{escape(match[1])}<br>{match[2]} · {match[3]}<br>{escape(match[4])}<br><br><a href="{board}">PREVIEW SCOREBOARD</a></div>'''

    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cricket Match Selector</title><style>body{{margin:0;background:#080d16;color:#fff;font-family:Arial,sans-serif}}.wrap{{max-width:950px;margin:auto;padding:22px 16px 50px}}h1{{margin:0 0 8px}}h2{{margin-top:30px;border-bottom:1px solid #33404f;padding-bottom:10px}}.card{{background:#141c28;border:1px solid #2c3949;border-radius:14px;padding:20px;margin:14px 0}}.live{{color:#20e878;font-weight:900;font-size:13px}}.up{{color:#ffd21a;font-weight:900;font-size:13px}}.title{{font-size:20px;font-weight:900;margin:10px 0 14px}}.date{{color:#ffd21a;font-weight:900;font-size:17px}}.venue{{color:#b8c4d3;margin:7px 0 15px}}button,a{{display:inline-block;padding:12px 18px;border:0;border-radius:8px;background:#00c853;color:#fff;font-weight:900;text-decoration:none}}.blue{{background:#1677ff}}.empty{{padding:22px;background:#141c28;border-radius:12px;color:#9da8b6}}.selected{{background:#162846;border:1px solid #1677ff;border-radius:12px;padding:18px;line-height:1.7;margin:18px 0}}</style></head><body><div class="wrap"><h1>🏏 CRICKET MATCH SELECTOR</h1><p>Select a live match or prepare an upcoming match for the OBS overlay.</p>{selected_html}<h2>🔴 Live Matches</h2>{live_html}<h2>🕒 Upcoming Matches</h2>{upcoming_html}</div></body></html>'''
    return Response(html, mimetype="text/html")

# Replace the existing Flask endpoint cleanly.
app.view_functions["select_match"] = selector
