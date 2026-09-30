# Render production entrypoint: keep the match selector and use the live-data WSGI scoreboard.
import selector
import wsgi

app = wsgi.app
