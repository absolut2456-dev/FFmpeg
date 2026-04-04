import os
import subprocess
import uuid
import requests
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

TEMP_DIR = "/tmp/video_renders"
os.makedirs(TEMP_DIR, exist_ok=True)

def download_file(url, dest_dir, prefix):
    if not url:
        return None
    local_filename = os.path.join(dest_dir, f"{prefix}_{uuid.uuid4()}.tmp")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

@app.route('/render', methods=['POST'])
def render_video():
    # Логируем заголовки и тело
    print("=== New request ===")
    print(f"Headers: {dict(request.headers)}")
    print(f"Content-Type: {request.content_type}")
    try:
        data = request.get_json()
        print(f"JSON data: {data}")
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return jsonify({"error": "Invalid JSON"}), 400

    if not data:
        return jsonify({"error": "No JSON data"}), 400

    video_url = data.get('video_url')
    voice_url = data.get('voice_url')
    music_url = data.get('music_url')

    print(f"video_url: {video_url}")
    print(f"voice_url: {voice_url}")
    print(f"music_url: {music_url}")

    if not video_url:
        print("ERROR: video_url is missing")
        return jsonify({"error": "video_url is required"}), 400

    try:
        video_path = download_file(video_url, TEMP_DIR, "video")
        voice_path = download_file(voice_url, TEMP_DIR, "voice") if voice_url else None
        music_path = download_file(music_url, TEMP_DIR, "music") if music_url else None

        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(TEMP_DIR, output_filename)

        command = ['ffmpeg', '-i', video_path]
        if voice_path:
            command += ['-i', voice_path]
        if music_path:
            command += ['-i', music_path]

        command += ['-c:v', 'copy']

        if voice_path and music_path:
            command += [
                '-filter_complex',
                '[1:a]volume=1.0[voice];[2:a]volume=0.3[music];[voice][music]amix=inputs=2:duration=longest[aout]',
                '-map', '0:v:0', '-map', '[aout]', '-c:a', 'aac', '-shortest'
            ]
        elif voice_path:
            command += ['-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-shortest']
        elif music_path:
            command += ['-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-shortest']
        else:
            command += ['-an', '-shortest']

        command += ['-y', output_path]
        print(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Render successful, sending file {output_path}")
        return send_file(output_path, as_attachment=True, download_name='rendered_video.mp4')

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr}")
        return jsonify({"error": f"FFmpeg failed: {e.stderr}"}), 500
    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
