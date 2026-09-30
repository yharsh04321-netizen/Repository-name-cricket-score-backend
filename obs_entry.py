# Stable Render entrypoint for the Cricket Match Selector + OBS scoreboard.
# The Render service can keep using: gunicorn obs_entry:app --bind 0.0.0.0:$PORT
# The root URL opens the selector, and the selected match ID is carried into OBS.

from flask import request, redirect, jsonify
import selector_entry
import main

app = selector_entry.app


def _selected_score():
    mid = str(request.args.get("match_id", "")).strip()
    if not mid.isdigit():
        return jsonify({"match": None, "error": "match_id is required"}), 400

    try:
        match = next(
            (m for m in selector_entry.get_matches() if str(m.get("id")) == mid),
            {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"},
        )
    except Exception:
        match = {"id": mid, "name": f"Match {mid}", "url": f"https://www.cricbuzz.com/live-cricket-scores/{mid}"}

    data = None
    try:
        # Use the tolerant production parser directly. It does not depend on
        # the old scorecard_url/team_code helpers.
        data = main.live_detail(mid)
        if isinstance(data, dict):
            data["url"] = match.get("url", data.get("url", ""))
            data.setdefault("current_over", {"over": "", "balls": [], "free_hit": False, "last_ball": ""})
    except Exception as exc:
        print("selected-score main parser failed:", repr(exc))

    if data is None:
        try:
            data = selector_entry._fallback_live(match)
        except Exception as exc:
            print("selected-score fallback failed:", repr(exc))

    response = jsonify({"match": data, "error": None if data else "live score temporarily unavailable"})
    for key, value in {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Vary": "*",
    }.items():
        response.headers[key] = value
    return response


# Replace any older selected-score handler with the stable one.
for rule in list(app.url_map.iter_rules()):
    if rule.rule == "/selected-score":
        app.view_functions[rule.endpoint] = _selected_score
        break
else:
    app.add_url_rule("/selected-score", endpoint="obs_selected_score", view_func=_selected_score, methods=["GET"])


# Make the primary Render URL useful: opening the service goes straight to the
# match selector instead of showing the backend JSON health response.
@app.route("/cricket-selector")
def cricket_selector():
    return redirect("/select-match")


@app.route("/", endpoint="obs_home")
def obs_home():
    return redirect("/select-match")


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
