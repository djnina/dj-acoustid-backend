from flask import Flask, request, jsonify
import requests
import tempfile
import os

app = Flask(__name__)

AUDD_API_KEY = os.getenv("AUDD_API_KEY")


@app.route("/")
def home():
    return "DJ AudD backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    # -------------------------
    # 🔐 API KEY CHECK
    # -------------------------
    if not AUDD_API_KEY:
        return jsonify({"error": "Missing AUDD_API_KEY"}), 500

    # -------------------------
    # 📦 FILE CHECK
    # -------------------------
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    audio = request.files["file"]

    # -------------------------
    # 💾 TEMP FILE
    # -------------------------
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio.save(tmp.name)

    try:
        # -------------------------
        # 🚀 AUDD REQUEST
        # -------------------------
        with open(tmp.name, "rb") as f:
            res = requests.post(
                "https://api.audd.io/",
                data={
                    "api_token": AUDD_API_KEY,
                    "return": "spotify,apple_music"
                },
                files={
                    "file": f
                },
                timeout=15
            )

        data = res.json()

        print("===== AUDD RESPONSE =====")
        print(data)
        print("=========================")

        # -------------------------
        # ❌ API ERROR CHECK
        # -------------------------
        if data.get("status") == "error":
            return jsonify({
                "error": "AudD API error",
                "response": data
            }), 500

        result = data.get("result")

        if not result:
            return jsonify({
                "error": "no match found",
                "raw_response": data
            })

        return jsonify({
            "title": result.get("title", "Unknown"),
            "artist": result.get("artist", "Unknown"),
            "album": result.get("album", "Unknown"),
            "spotify": result.get("spotify", {}).get("external_urls", {}).get("spotify")
        })

    except Exception as e:
        return jsonify({
            "error": "AudD request failed",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
