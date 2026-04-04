import os
import subprocess
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Инициализация приложения
app = Flask(__name__)
CORS(app)

# Папка для временного хранения файлов
TEMP_DIR = "/tmp/video_renders"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.route('/render', methods=['POST'])
def render_video():
    """
    Эндпоинт для генерации видео. Ждёт JSON с ссылками на видео и аудио.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    video_url = data.get('video_url')
    audio_url = data.get('audio_url')
    output_filename = f"{uuid.uuid4()}.mp4"
    output_path = os.path.join(TEMP_DIR, output_filename)

    # 1. Скачиваем файлы
    try:
        video_path = download_file(video_url, TEMP_DIR, "video")
        audio_path = download_file(audio_url, TEMP_DIR, "audio")
    except Exception as e:
        return jsonify({"error": f"File download failed: {str(e)}"}), 500

    # 2. Выполняем склейку через FFmpeg
    try:
        command = [
            'ffmpeg',
            '-i', video_path,   # входной видеофайл
            '-i', audio_path,   # входной аудиофайл
            '-c:v', 'copy',     # копируем видео без перекодировки (быстро)
            '-c:a', 'aac',      # перекодируем аудио в AAC
            '-map', '0:v:0',    # берём видео из первого входного файла
            '-map', '1:a:0',    # берём аудио из второго входного файла
            '-shortest',        # обрезаем по самой короткой дорожке
            '-y',               # перезаписывать выходной файл, если он существует
            output_path
        ]
        # Выполняем команду в системе
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        # Если FFmpeg завершился с ошибкой, возвращаем её
        return jsonify({"error": f"FFmpeg failed: {e.stderr}"}), 500

    # 3. Отдаём готовый видеофайл
    return send_file(output_path, as_attachment=True, download_name='rendered_video.mp4')

def download_file(url, dest_dir, prefix):
    """Скачивает файл по URL и сохраняет его во временную папку."""
    # Генерируем уникальное имя для файла
    local_filename = os.path.join(dest_dir, f"{prefix}_{uuid.uuid4()}.tmp")
    # Скачиваем файл потоково
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

from flask import send_file

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
