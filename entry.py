# Render production entrypoint: keep the live-data WSGI scoreboard.
import time
import wsgi

app = wsgi.app


@app.after_request
def _obs_live_no_cache(response):
    """Prevent OBS/browser caching and force fresh selected-score requests."""
    path = ""
    try:
        path = app.request_class.environ.get("PATH_INFO", "")
    except Exception:
        pass

    # Flask exposes request context; import lazily so the module stays simple.
    try:
        from flask import request
        path = request.path
    except Exception:
        pass

    if path in ("/scoreboard", "/selected-score"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    if path == "/scoreboard" and response.status_code == 200:
        try:
            html = response.get_data(as_text=True)
            # This runs BEFORE the scoreboard's own JavaScript because it is
            # injected at the start of <head>. Every selected-score fetch gets
            # a unique query parameter and cache:'no-store'.
            refresh_script = r'''<script>
(function(){
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function(input, init){
    try {
      let url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
      if (url.indexOf('/selected-score?') !== -1) {
        const sep = url.indexOf('?') === -1 ? '?' : '&';
        url += sep + '_live_ts=' + Date.now();
        init = Object.assign({}, init || {}, {cache:'no-store'});
        return nativeFetch(url, init);
      }
    } catch(e) {}
    return nativeFetch(input, init);
  };
})();
</script>'''
            if "</head>" in html:
                html = html.replace("</head>", refresh_script + "</head>", 1)
                response.set_data(html)
        except Exception as exc:
            print("OBS cache-buster injection error:", repr(exc))

    return response
