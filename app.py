from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile
import shutil
import os

app = Flask(__name__)

# ✅ Use environment variable instead of hardcoding
ACOUSTID_KEY = os.getenv("ACOUSTID_KEY")


@app.route("/")
def home():
    return "DJ AcoustID backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    # 1. Validate file
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    if not ACOUSTID_KEY:
        return jsonify({"error": "Missing ACOUSTID_KEY"}), 500

    audio = request.files["file"]

    # 2. Find fpcalc dynamically (works with Docker)
    fpcalc_path = shutil.which("fpcalc")
    if not fpcalc_path:
        return jsonify({
            "error": "fpcalc not installed or not in PATH"
        }), 500

    # 3. Save temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        audio.save(tmp.name)

        # 4. Run fingerprint tool
        try:
            result = subprocess.run(
                [fpcalc_path, tmp.name],
                capture_output=True,
                text=True,
                check=True
            )
        except Exception as e:
            return jsonify({
                "error": "fpcalc failed",
                "details": str(e)
            }), 500

    fingerprint = None
    duration = None

    for line in result.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1]
        if line.startswith("DURATION="):
            duration = line.split("=", 1)[1]

    # 5. Validate fingerprint
    if not fingerprint or not duration:
        return jsonify({
            "error": "fingerprint extraction failed"
        }), 500

    # 6. Call AcoustID API
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

        track = (
            data.get("results", [{}])[0]
                .get("recordings", [{}])[0]
        )

        return jsonify({
            "title": track.get("title", "Unknown"),
            "artist": (
                track.get("artists", [{}])[0].get("name", "Unknown")
                if track.get("artists") else "Unknown"
            )
        })

    except Exception as e:
        return jsonify({
            "error": "AcoustID request failed",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    # Render/Docker uses PORT env variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
