# Render production entrypoint: keep the live-data WSGI scoreboard.
import wsgi
from flask import request, jsonify

app = wsgi.app


def _obs_selected_score():
    """Dedicated JSON endpoint used by the OBS scoreboard.

    Some versions of the original Flask app did not expose the selected-score
    route on the production entrypoint, leaving OBS permanently on
    'LOADING LIVE SCORE'. Always resolve the requested match through the live
    WSGI implementation and return JSON.
    """
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
        return response
    except Exception as exc:
        print("OBS selected-score error:", repr(exc))
        response = jsonify({"match": None, "error": "live score temporarily unavailable"})
        response.status_code = 200
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


# Replace an existing selected-score handler if one exists; otherwise create it.
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
    """Prevent OBS/browser caching and force the scoreboard to re-open fresh data."""
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
  // OBS Chromium can keep the scoreboard document alive while its internal
  // fetch loop gets stale. Force a clean document reload every 5 seconds.
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
