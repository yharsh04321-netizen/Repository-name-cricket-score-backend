# Render production entrypoint: keep the live-data WSGI scoreboard.
import time
import requests
import wsgi
from flask import request, jsonify

app = wsgi.app

# OBS must receive a fresh upstream snapshot. Cricbuzz's live-center endpoint
# can be CDN-cached, so every server-side poll gets a unique query string.
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
    """Dedicated no-cache JSON endpoint used by the OBS scoreboard."""
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
            # Do NOT force a full-page reload. OBS Chromium can keep a browser
            # source alive and a document reload can reset the overlay state.
            # Instead, patch fetch() so the scoreboard's existing polling loop
            # always asks our JSON endpoint for a genuinely fresh response.
            client_script = r'''<script>
(function(){
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function(input, init){
    try {
      let url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
      if (url.indexOf('/selected-score') !== -1) {
        const u = new URL(url, window.location.href);
        u.searchParams.set('_obs_client_ts', Date.now().toString());
        u.searchParams.set('_obs_client_rand', Math.random().toString(36).slice(2));
        if (typeof input === 'string') input = u.toString();
        else input = new Request(u.toString(), input);
        init = Object.assign({}, init || {}, {cache:'no-store'});
      }
    } catch(e) {}
    return nativeFetch(input, init);
  };

  // Watchdog: if the scoreboard's own polling loop stops, poll the JSON
  // endpoint independently. This does not reload the page and is OBS-safe.
  const mid = new URLSearchParams(window.location.search).get('match_id') || '';
  let lastJson = '';
  async function obsWatchdog(){
    if(!mid) return;
    try{
      const u = new URL('/selected-score', window.location.origin);
      u.searchParams.set('match_id', mid);
      u.searchParams.set('_obs_watchdog', Date.now().toString());
      const r = await nativeFetch(u.toString(), {cache:'no-store', headers:{'Cache-Control':'no-cache'}});
      if(!r.ok) return;
      const data = await r.json();
      const current = JSON.stringify(data && data.match ? data.match : data);
      if(current && current !== lastJson){
        lastJson = current;
        // The normal scoreboard polling code consumes this endpoint. Dispatch
        // a custom event as an additional signal for future render handlers.
        window.dispatchEvent(new CustomEvent('obs-live-score', {detail:data}));
      }
    }catch(e){}
  }
  obsWatchdog();
  setInterval(obsWatchdog, 3000);
})();
</script>'''
            if "</head>" in html:
                html = html.replace("</head>", client_script + "</head>", 1)
                response.set_data(html)
        except Exception as exc:
            print("OBS live polling injection error:", repr(exc))

    return response
