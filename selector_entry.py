# Render entrypoint for the live match selector + production OBS scoreboard.
# The selector must use entry.app so the production live-score fixes are loaded.
from flask import Response, request
from urllib.parse import quote
import re
import requests
from bs4 import BeautifulSoup
import entry
import main

app = entry.app

SELECTOR_SOURCES = [
    "https://www.cricbuzz.com/cricket-match/live-scores/recent-matches",
    "https://m.cricbuzz.com/cricket-match/live-scores/recent-matches",
]
HEADERS = dict(main.HEADERS)


def get_matches():
    matches = []
    seen = set()
    for url in SELECTOR_SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select('a[href*="/live-cricket-scores/"]'):
                href = a.get("href", "")
                m = re.search(r"/live-cricket-scores/(\d+)(?:/([^?#]+))?", href)
                if not m:
                    continue
                mid = m.group(1)
                if mid in seen:
                    continue
                text = " ".join(a.stripped_strings)
                if not text:
                    text = (m.group(2) or "").replace("-", " ").strip()
                if not text:
                    continue
                low = text.lower()
                if any(x in low for x in ("scorecard", "commentary", "squads", "overs", "graphs")):
                    continue
                seen.add(mid)
                matches.append({"id": mid, "name": text[:180]})
        except Exception as exc:
            print("selector source error:", repr(exc))

        if len(matches) >= 8:
            break

    fallback = [
        {"id": "151543", "name": "India vs West Indies — 2nd ODI"},
        {"id": "151532", "name": "India vs West Indies — 1st ODI"},
    ]
    for item in fallback:
        if item["id"] not in seen:
            matches.insert(0, item)
            seen.add(item["id"])
    return matches[:30]


def select_match():
    selected = request.args.get("selected", "")
    matches = get_matches()
    cards = []
    for m in matches:
        mid = m["id"]
        name = m["name"]
        cards.append(f'''<div class="card"><div class="name">{name}</div><div class="id">Match ID: {mid}</div><a class="btn" href="/scoreboard?match_id={quote(mid)}">SELECT THIS MATCH</a></div>''')
    selected_html = f'<div class="selected">Selected: {selected}</div>' if selected else ''
    body = "".join(cards) or '<div class="empty">No matches found. Tap REFRESH to try again.</div>'
    html = f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cricket Match Selector</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#0b0f14;color:#fff;font-family:Arial,sans-serif;padding:18px}}h1{{font-size:24px;margin:4px 0 6px}}.sub{{color:#9aa4b2;font-size:13px;margin-bottom:14px}}.top{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.refresh,.home{{display:inline-block;padding:11px 15px;border-radius:9px;text-decoration:none;font-weight:700}}.refresh{{background:#00c853;color:#001b0a}}.home{{background:#202936;color:#fff}}.selected{{background:#122a1b;border:1px solid #00c853;padding:10px;border-radius:9px;margin-bottom:12px}}.card{{background:#151c25;border:1px solid #293443;border-radius:13px;padding:15px;margin:10px 0}}.name{{font-size:17px;font-weight:700;line-height:1.3}}.id{{color:#8d99a8;font-size:12px;margin:7px 0 12px}}.btn{{display:block;text-align:center;background:#00c853;color:#001b0a;text-decoration:none;font-weight:800;padding:12px;border-radius:9px}}.empty{{padding:30px 10px;text-align:center;color:#aab3bf}}
</style></head><body><h1>🏏 Cricket Match Selector</h1><div class="sub">Choose the match you want to send to your live scoreboard / OBS.</div><div class="top"><a class="refresh" href="/select-match">↻ REFRESH MATCHES</a><a class="home" href="/">Backend status</a></div>{selected_html}{body}</body></html>'''
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})

# Replace only the selector route; entry.app keeps the production live scoreboard.
app.view_functions["select_match"] = select_match

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
