# Render production entrypoint: keep the live-data WSGI scoreboard.
import time
import requests
import wsgi
from flask import request, jsonify

app = wsgi.app

# IMPORTANT: the upstream Cricbuzz live-center response can be cached even when
# our own Render response is no-cache. Give every upstream request a unique URL
# so each OBS refresh gets a fresh live snapshot.
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
    })
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Keep the WSGI cache in sync for any other code path, but do not use it
        # as the source of truth for the OBS endpoint.
        wsgi.LIVE_CACHE[mid] = {"time": time.time(), "data": data}
        return data
    except Exception as exc:
        print("fresh live center error:", repr(exc))
        cached = wsgi.LIVE_CACHE.get(mid)
        return cached["data"] if cached else None

# _extract_live resolves _live_data from the wsgi module globals, so replacing
# this function here makes the production OBS endpoint fetch fresh upstream data.
wsgi._live_data = _obs_fresh_live_data


def _obs_selected_score():
    """Dedicated JSON endpoint used by the OBS scoreboard."""
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
            refresh_script = r'''<script>
(function(){
  // Reload the scoreboard document every 5 seconds. Each reload gets a fresh
  // timestamp and the server fetches a fresh upstream live snapshot.
  const INTERVAL = 5000;
  setInterval(function(){
    try {
      const u = new URL(window.location.href);
      u.searchParams.set('_obs_live_ts', Date.now().toString());
      window.location.replace(u.toString());
    } catch(e) {
      window.location.reload();
    }
  }, INTERVAL);
})();
</script>'''
            if "</head>" in html:
                html = html.replace("</head>", refresh_script + "</head>", 1)
                response.set_data(html)
        except Exception as exc:
            print("OBS refresh injection error:", repr(exc))

    return response
