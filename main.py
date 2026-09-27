@app.route("/debug-match")
def debug_match():
    import requests

    url = "https://www.cricbuzz.com/"
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        )
    }

    r = requests.get(url, headers=headers, timeout=20)

    html = r.text

    # Find the India vs West Indies section
    pos = html.find("West Indies tour of India")

    if pos == -1:
        pos = html.find("West Indies")

    if pos == -1:
        return {
            "success": False,
            "message": "Match text not found",
            "page_length": len(html)
        }

    return {
        "success": True,
        "position": pos,
        "html_length": len(html),
        "section": html[max(0, pos - 3000):pos + 10000]
    }
