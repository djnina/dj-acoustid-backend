from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile
import shutil
import os

app = Flask(__name__)

ACOUSTID_KEY = os.getenv("ACOUSTID_KEY")


@app.route("/")
def home():
    return "DJ AcoustID backend is running"


@app.route("/identify", methods=["POST"])
def identify():

    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    if not ACOUSTID_KEY:
        return jsonify({"error": "Missing ACOUSTID_KEY"}), 500

    audio = request.files["file"]

    fpcalc_path = shutil.which("fpcalc")
    ffmpeg_path = shutil.which("ffmpeg")

    if not fpcalc_path:
        return jsonify({"error": "fpcalc not installed"}), 500

    if not ffmpeg_path:
        return jsonify({"error": "ffmpeg not installed"}), 500

    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp_in:
        audio.save(tmp_in.name)

    # =========================
    # 🔥 STEP 1: convert to WAV
    # =========================
    wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i", tmp_in.name,
                "-ac", "1",
                "-ar", "44100",
                wav_file
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except Exception as e:
        return jsonify({
            "error": "ffmpeg conversion failed",
            "details": str(e)
        }), 500

    # =========================
    # 🔥 STEP 2: fpcalc on WAV
    # =========================
    try:
        result = subprocess.run(
            [fpcalc_path, wav_file],
            capture_output=True,
            text=True,
            check=True
        )
    except Exception as e:
        return jsonify({
            "error": "fpcalc failed",
            "details": str(e)
        }), 500

    print("===== FPCALC OUTPUT =====")
    print(result.stdout)
    print("=========================")

    fingerprint = None
    duration = None

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

    # =========================
    # 🔥 STEP 3: AcoustID API
    # =========================
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

        results = data.get("results", [])

        track = None
        score = None

        for r in results:
            if "recordings" in r and r["recordings"]:
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
