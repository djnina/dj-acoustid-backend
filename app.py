from flask import Flask, request, jsonify
import subprocess
import requests
import tempfile

app = Flask(__name__)

ACOUSTID_KEY = "W6n6qmPt8U"

@app.route("/identify", methods=["POST"])
def identify():

    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    audio = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp:
        audio.save(tmp.name)

        result = subprocess.run(
            ["fpcalc", tmp.name],
            capture_output=True,
            text=True
        )

        fingerprint = None
        duration = None

        for line in result.stdout.split("\n"):
            if line.startswith("FINGERPRINT="):
                fingerprint = line.split("=")[1]
            if line.startswith("DURATION="):
                duration = line.split("=")[1]

        if not fingerprint:
            return jsonify({"error": "fingerprint failed"}), 500

        res = requests.get("https://api.acoustid.org/v2/lookup", params={
            "client": ACOUSTID_KEY,
            "fingerprint": fingerprint,
            "duration": duration,
            "meta": "recordings"
        })

        data = res.json()

        try:
            track = data["results"][0]["recordings"][0]
            return jsonify({
                "title": track["title"],
                "artist": track["artists"][0]["name"]
            })

        except:
            return jsonify({
                "title": "Unknown",
                "artist": "Unknown"
            })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
