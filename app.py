import os
import subprocess
import uuid
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

TEMP_DIR = "/tmp/video_renders"
os.makedirs(TEMP_DIR, exist_ok=True)

def download_file(url, dest_dir, prefix):
    """Скачивает файл по URL и возвращает локальный путь."""
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
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    video_url = data.get('video_url')
    voice_url = data.get('voice_url')   # озвучка (основной звук)
    music_url = data.get('music_url')   # фоновая музыка

    if not video_url:
        return jsonify({"error": "video_url is required"}), 400

    try:
        # 1. Скачиваем все файлы
        video_path = download_file(video_url, TEMP_DIR, "video")
        voice_path = download_file(voice_url, TEMP_DIR, "voice") if voice_url else None
        music_path = download_file(music_url, TEMP_DIR, "music") if music_url else None

        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(TEMP_DIR, output_filename)

        # 2. Строим команду FFmpeg
        # Базовый фильтр: копируем видео
        command = ['ffmpeg', '-i', video_path]

        # Добавляем аудио входы
        if voice_path:
            command += ['-i', voice_path]
        if music_path:
            command += ['-i', music_path]

        # Параметры кодирования
        command += ['-c:v', 'copy']  # видео копируем без изменений

        if voice_path and music_path:
            # Два аудио: голос + музыка (музыку делаем тише)
            # amix: смешивает два потока, duration=longest (длина по самому длинному)
            # volume=0.3 для музыки (30% громкости)
            command += [
                '-filter_complex',
                '[1:a]volume=1.0[voice];[2:a]volume=0.3[music];[voice][music]amix=inputs=2:duration=longest[aout]',
                '-map', '0:v:0',      # видео
                '-map', '[aout]',     # смешанное аудио
                '-c:a', 'aac',
                '-shortest'
            ]
        elif voice_path:
            # Только голос
            command += ['-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-shortest']
        elif music_path:
            # Только музыка
            command += ['-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-shortest']
        else:
            # Нет аудио
            command += ['-an', '-shortest']

        command += ['-y', output_path]

        # Выполняем
        subprocess.run(command, check=True, capture_output=True, text=True)

        return send_file(output_path, as_attachment=True, download_name='rendered_video.mp4')

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"FFmpeg failed: {e.stderr}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
