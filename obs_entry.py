# Stable Render entrypoint for the Cricket Match Selector + OBS scoreboard.
from flask import request, redirect, jsonify
import selector_entry
import main

app = selector_entry.app


def _selected_score():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return jsonify({"match": None, "error": "match_id is required"}), 400
    try:
        match = next((m for m in selector_entry.get_matches() if str(m.get("id")) == mid), {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"})
    except Exception:
        match = {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}
    data = None
    try:
        data = main.live_detail(mid)
    except Exception as exc:
        print("selected-score main parser failed:", repr(exc))
    if data is None:
        try:
            data = selector_entry._fallback_live(match)
        except Exception as exc:
            print("selected-score fallback failed:", repr(exc))
    response = jsonify({"match": data, "error": None if data else "live score temporarily unavailable"})
    for k, v in {"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0", "Pragma":"no-cache", "Expires":"0", "Vary":"*"}.items():
        response.headers[k] = v
    return response


# entry.py already owns the Flask app, so defining another @app.route('/') does
# not replace its existing health endpoint. Explicitly replace the registered
# view function instead.
def _home():
    return redirect("/select-match")

for rule in list(app.url_map.iter_rules()):
    if rule.rule == "/":
        app.view_functions[rule.endpoint] = _home
    elif rule.rule == "/selected-score":
        app.view_functions[rule.endpoint] = _selected_score

# Ensure these routes exist even if an older entry.py version is deployed.
if not any(r.rule == "/selected-score" for r in app.url_map.iter_rules()):
    app.add_url_rule("/selected-score", endpoint="obs_selected_score", view_func=_selected_score, methods=["GET"])
if not any(r.rule == "/cricket-selector" for r in app.url_map.iter_rules()):
    app.add_url_rule("/cricket-selector", endpoint="obs_selector", view_func=lambda: redirect("/select-match"), methods=["GET"])

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
