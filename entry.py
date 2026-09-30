# Render production entrypoint: keep the live-data WSGI scoreboard.
import time
import requests
import wsgi
from flask import request, jsonify

app = wsgi.app

def _obs_fresh_live_data(match):
    mid = wsgi._match_id(match)
    if not mid:
        return None
    url = wsgi.LIVE_URL.format(mid) + "?obs_ts=" + str(time.time_ns())
    headers = dict(wsgi.HEADERS)
    headers.update({
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (cricket-live-overlay/1.0)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cricbuzz.com/",
        "Origin": "https://www.cricbuzz.com",
    })
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        wsgi.LIVE_CACHE[mid] = {"time": time.time(), "data": data}
        return data
    except Exception as exc:
        print("fresh live center error:", repr(exc))
        cached = wsgi.LIVE_CACHE.get(mid)
        return cached["data"] if cached else None

wsgi._live_data = _obs_fresh_live_data


def _obs_selected_score():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid:
        return jsonify({"match": None, "error": "match_id is required"}), 400
    try:
        match = wsgi.main.get_match_by_id(mid)
        data = wsgi._fetch_match_detail(match)
        response = jsonify({"match": data})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Vary"] = "*"
        return response
    except Exception as exc:
        print("OBS selected-score error:", repr(exc))
        response = jsonify({"match": None, "error": "live score temporarily unavailable"})
        response.status_code = 200
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

_selected_endpoint = None
for _rule in app.url_map.iter_rules():
    if _rule.rule == "/selected-score":
        _selected_endpoint = _rule.endpoint
        break

if _selected_endpoint:
    app.view_functions[_selected_endpoint] = _obs_selected_score
else:
    app.add_url_rule("/selected-score", endpoint="selected_score", view_func=_obs_selected_score, methods=["GET"])

@app.after_request
def _obs_live_no_cache(response):
    path = request.path
    if path in ("/scoreboard", "/selected-score"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Vary"] = "*"

    if path == "/scoreboard" and response.status_code == 200:
        try:
            html = response.get_data(as_text=True)
            # The previous watchdog fetched fresh JSON but did not itself update
            # the scoreboard DOM. For OBS reliability, reload the document every
            # 5 seconds with a unique query string. This guarantees the rendered
            # scoreboard starts from a fresh server snapshot without relying on
            # internal DOM IDs or the page's own polling implementation.
            client_script = r'''<script>
(function(){
  const params = new URLSearchParams(window.location.search);
  const mid = params.get('match_id') || '';
  if(!mid) return;
  let reloading = false;
  setTimeout(function(){
    if(reloading) return;
    reloading = true;
    const next = '/scoreboard?match_id=' + encodeURIComponent(mid) + '&_obs_live=' + Date.now();
    window.location.replace(next);
  }, 5000);
})();
</script>'''
            if "</head>" in html:
                html = html.replace("</head>", client_script + "</head>", 1)
                response.set_data(html)
        except Exception as exc:
            print("OBS live reload injection error:", repr(exc))
    return response
