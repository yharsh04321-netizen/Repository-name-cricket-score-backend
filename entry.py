# Render production entrypoint: keep the live-data WSGI scoreboard.
import wsgi
from flask import request

app = wsgi.app


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
  // The server sends no-cache headers, so each reload requests a fresh score.
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
