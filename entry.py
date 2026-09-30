# Render production entrypoint: keep the live-data WSGI scoreboard.
import wsgi
from flask import request

app = wsgi.app


@app.after_request
def _obs_live_no_cache(response):
    """Prevent OBS/browser caching and force fresh selected-score requests."""
    path = request.path

    if path in ("/scoreboard", "/selected-score"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    if path == "/scoreboard" and response.status_code == 200:
        try:
            html = response.get_data(as_text=True)
            # Install this before the scoreboard's own JavaScript executes.
            # Every selected-score request gets a unique timestamp and
            # cache:'no-store', so OBS cannot keep an old score snapshot.
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
