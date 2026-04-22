from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile
import shutil
import os
import json

app = Flask(__name__)

ACOUSTID_KEY = os.getenv("ACOUSTID_KEY")


@app.route("/")
def home():
    return "DJ AcoustID backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    # -------------------------
    # 🔐 API KEY CHECK
    # -------------------------
    if not ACOUSTID_KEY:
        return jsonify({"error": "Missing ACOUSTID_KEY env var"}), 500

    if len(ACOUSTID_KEY) < 10:
        return jsonify({
            "error": "Invalid ACOUSTID_KEY (too short)",
            "hint": "Use key from acoustid.org/api-key"
        }), 500

    # -------------------------
    # 📦 FILE CHECK
    # -------------------------
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    audio = request.files["file"]

    # -------------------------
    # fpcalc check
    # -------------------------
    fpcalc_path = shutil.which("fpcalc")
    if not fpcalc_path:
        return jsonify({"error": "fpcalc not installed"}), 500

    # -------------------------
    # TEMP FILE
    # -------------------------
    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp:
        audio.save(tmp.name)

        try:
            result = subprocess.run(
                [fpcalc_path, "-json", tmp.name],
                capture_output=True,
                text=True,
                timeout=10
            )
        except Exception as e:
            return jsonify({"error": "fpcalc failed", "details": str(e)}), 500

    # -------------------------
    # DEBUG OUTPUT
    # -------------------------
    print("===== FPCALC OUTPUT =====")
    print(result.stdout)
    print("=========================")

    # -------------------------
    # PARSE FINGERPRINT
    # -------------------------
    fingerprint = None
    duration = None

    try:
        data = json.loads(result.stdout)
        fingerprint = data.get("fingerprint")
        duration = data.get("duration")
    except Exception:
        for line in result.stdout.splitlines():
            if line.startswith("FINGERPRINT="):
                fingerprint = line.split("=", 1)[1]
            if line.startswith("DURATION="):
                duration = line.split("=", 1)[1]

    if not fingerprint or not duration:
        return jsonify({
            "error": "fingerprint extraction failed",
            "debug": result.stdout
        }), 500

    # -------------------------
    # 🔎 ACOUTSTID REQUEST
    # -------------------------
    try:
        res = requests.get(
            "https://api.acoustid.org/v2/lookup",
            params={
                "client": ACOUSTID_KEY,
                "fingerprint": fingerprint,
                "duration": duration,
                "meta": "recordings"
            },
            timeout=10
        )

        data = res.json()

        print("===== ACOUSTID RESPONSE =====")
        print(data)
        print("=============================")

        # -------------------------
        # ❌ API ERROR HANDLING
        # -------------------------
        if data.get("status") == "error":
            return jsonify({
                "error": "AcoustID API error",
                "response": data
            }), 500

        results = data.get("results", [])

        track = None
        score = None

        for r in results:
            if r.get("recordings"):
                track = r["recordings"][0]
                score = r.get("score")
                break

        if not track:
            return jsonify({
                "error": "no match found",
                "raw_response": data
            })

        return jsonify({
            "title": track.get("title", "Unknown"),
            "artist": (
                track.get("artists", [{}])[0].get("name", "Unknown")
                if track.get("artists") else "Unknown"
            ),
            "score": score
        })

    except Exception as e:
        return jsonify({
            "error": "AcoustID request failed",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
