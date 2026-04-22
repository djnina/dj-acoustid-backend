from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile
import shutil
import os
import json

app = Flask(__name__)

# 🔑 Load API key safely
ACOUSTID_KEY = os.environ.get("ACOUSTID_KEY", "").strip()

# 🔍 startup debug (Render log check)
print("🔑 ACOUSTID KEY LOADED:", bool(ACOUSTID_KEY))


@app.route("/")
def home():
    return "DJ AcoustID backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    # 1. Validate file
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    if not ACOUSTID_KEY:
        return jsonify({"error": "Missing or invalid ACOUSTID_KEY"}), 500

    audio = request.files["file"]

    # 2. Check fpcalc
    fpcalc_path = shutil.which("fpcalc")
    if not fpcalc_path:
        return jsonify({
            "error": "fpcalc not installed or not in PATH"
        }), 500

    # 3. Save temp file (iOS-safe format)
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
            return jsonify({
                "error": "fpcalc crashed",
                "details": str(e)
            }), 500

    # 🔍 DEBUG: fpcalc output
    print("===== FPCALC OUTPUT =====")
    print(result.stdout)
    print("=========================")

    # 4. Parse fingerprint
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

    print("Fingerprint:", fingerprint)
    print("Duration:", duration)

    if not fingerprint or not duration:
        return jsonify({
            "error": "fingerprint extraction failed",
            "debug": result.stdout
        }), 500

    # 5. Call AcoustID API
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

        # 🔥 FIX: handle API errors properly
        if res.status_code != 200:
            return jsonify({
                "error": "AcoustID API request failed",
                "status_code": res.status_code,
                "response": res.text
            }), 500

        try:
            data = res.json()
        except Exception:
            return jsonify({
                "error": "Invalid JSON from AcoustID",
                "raw": res.text
            }), 500

        print("===== ACOUSTID RESPONSE =====")
        print(data)
        print("=============================")

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
            }), 200

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
