from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile
import shutil

app = Flask(__name__)

ACOUSTID_KEY = "W6n6qmPt8U"


@app.route("/")
def home():
    return "DJ AcoustID backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    audio = request.files["file"]

    # ✅ find fpcalc dynamically (IMPORTANT)
    fpcalc_path = shutil.which("fpcalc")
    if not fpcalc_path:
        return jsonify({
            "error": "fpcalc not installed or not in PATH"
        }), 500

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        audio.save(tmp.name)

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

        if not fingerprint or not duration:
            return jsonify({
                "error": "fingerprint extraction failed"
            }), 500

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
    app.run(host="0.0.0.0", port=10000)
