import os
import cv2
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from ultralytics import YOLO
from werkzeug.utils import secure_filename
import json
from datetime import datetime
import uuid
import logging

import cv2
# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
HISTORY_FILE = 'history.json'

# Инициализация модели
try:
    MODEL = YOLO('best_truck.pt')

    logger.info("Модель YOLOv11 успешно загружена")
except Exception as err:
    logger.error(f"Ошибка при загрузке модели YOLO: {err}")
    MODEL = None

RTSP_STREAM = None


# Проверка допустимых расширений
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Сохранение истории в JSON
def save_history(data):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    history.append(data)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)


# Обработка изображения
def process_image(image_path):
    if MODEL is None:
        logger.error("Модель YOLO не инициализирована")
        return 0, None
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Не удалось загрузить изображение: {image_path}")
            return 0, None
        results = MODEL.predict(img, classes=[17], conf=0.005, verbose=False)  # Класс 7 = truck, conf=0.25
        if not results or not results[0].boxes:
            logger.warning(f"Грузовики не обнаружены на изображении: {image_path}")
            return 0, None
        count = len(results[0].boxes)
        # Логирование всех детектированных классов для диагностики
        detected_classes = results[0].boxes.cls.cpu().numpy().tolist() if results[0].boxes.cls is not None else []
        logger.info(f"Обработано изображение {image_path}: {count} грузовиков, классы: {detected_classes}")
        annotated_img = results[0].plot()
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"result_{os.path.basename(image_path)}")
        cv2.imwrite(output_path, annotated_img)
        return count, output_path
    except Exception as err:
        logger.error(f"Ошибка при обработке изображения {image_path}: {err}")
        return 0, None


# Обработка видео
def process_video(video_path):
    if MODEL is None:
        logger.error("Модель YOLO не инициализирована")
        return 0, None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Не удалось открыть видео: {video_path}")
            return 0, None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        truck_counts = []
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            results = MODEL.predict(frame, classes=[17], conf=0.005, verbose=False)  # Класс 17 = truck
            count = len(results[0].boxes) if results and results[0].boxes else 0
            truck_counts.append(count)
            # Логирование для каждого кадра
            detected_classes = results[0].boxes.cls.cpu().numpy().tolist() if results and results[
                0].boxes.cls is not None else []
            logger.info(f"Кадр {frame_idx} видео {video_path}: {count} грузовиков, классы: {detected_classes}")
            frame_idx += 1

        cap.release()
        avg_count = int(np.mean(truck_counts)) if truck_counts else 0
        logger.info(f"Обработано видео {video_path}: среднее количество грузовиков {avg_count}, кадры: {frame_count}")
        return avg_count, None  # Нет аннотированного видео для упрощения
    except Exception as err:
        logger.error(f"Ошибка при обработке видео {video_path}: {err}")
        return 0, None


# Обработка RTSP-потока
def process_rtsp():
    global RTSP_STREAM
    if not RTSP_STREAM:
        logger.error("RTSP-поток не указан")
        return 0, None
    if MODEL is None:
        logger.error("Модель YOLO не инициализирована")
        return 0, None
    try:
        cap = cv2.VideoCapture(RTSP_STREAM)
        if not cap.isOpened():
            logger.error(f"Не удалось открыть RTSP-поток: {RTSP_STREAM}")
            return 0, None
        ret, frame = cap.read()
        if not ret:
            cap.release()
            logger.error("Не удалось получить кадр из RTSP-потока")
            return 0, None
        results = MODEL.predict(frame, classes=[17], conf=0.005, verbose=False)  # Класс 17 = truck
        count = len(results[0].boxes) if results and results[0].boxes else 0
        detected_classes = results[0].boxes.cls.cpu().numpy().tolist() if results and results[
            0].boxes.cls is not None else []
        logger.info(f"RTSP-кадр: {count} грузовиков, классы: {detected_classes}")
        annotated_frame = results[0].plot()
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"rtsp_frame_{uuid.uuid4().hex}.jpg")
        cv2.imwrite(output_path, annotated_frame)
        cap.release()
        return count, output_path
    except Exception as err:
        logger.error(f"Ошибка при обработке RTSP-потока: {err}")
        return 0, None


# Генерация Excel-отчета
def generate_excel_report():
    if not os.path.exists(HISTORY_FILE):
        logger.warning("Файл истории не существует")
        return None
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        df = pd.DataFrame(history)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'report.xlsx')
        df.to_excel(output_path, index=False)
        logger.info(f"Сгенерирован отчет: {output_path}")
        return output_path
    except Exception as err:
        logger.error(f"Ошибка при генерации отчета: {err}")
        return None


# Главная страница
@app.route('/')
def index():
    return render_template('index.html')


# Загрузка и обработка файла
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logger.error("Файл не загружен в запросе")
        return jsonify({'error': 'Файл не загружен'}), 400
    file = request.files['file']
    if file.filename == '':
        logger.error("Файл не выбран")
        return jsonify({'error': 'Файл не выбран'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f"Файл сохранен: {file_path}")

        if filename.lower().endswith(('png', 'jpg', 'jpeg')):
            count, output_path = process_image(file_path)
        else:  # mp4
            count, output_path = process_video(file_path)

        history_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'filename': filename,
            'truck_count': count,
            'output_path': output_path if output_path else ''
        }
        save_history(history_entry)

        return jsonify({
            'count': count,
            'output_path': f'static/{output_path.replace("static/", "")}' if output_path else '',
            'history': history_entry
        })
    logger.error(f"Недопустимый формат файла: {file.filename}")
    return jsonify({'error': 'Недопустимый формат файла'}), 400


# Обработка RTSP-потока
@app.route('/process_rtsp', methods=['POST'])
def process_rtsp_route():
    global RTSP_STREAM
    RTSP_STREAM = request.form.get('rtsp_url', '')
    count, output_path = process_rtsp()

    history_entry = {
        'id': str(uuid.uuid4()),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'filename': 'RTSP_STREAM',
        'truck_count': count,
        'output_path': output_path if output_path else ''
    }
    save_history(history_entry)

    return jsonify({
        'count': count,
        'output_path': f'static/{output_path.replace("static/", "")}' if output_path else '',
        'history': history_entry
    })


# Получение истории
@app.route('/history', methods=['GET'])
def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        return jsonify(history)
    return jsonify([])


# Скачивание отчета
@app.route('/download_report', methods=['GET'])
def download_report():
    report_path = generate_excel_report()
    if report_path:
        return send_file(report_path, as_attachment=True)
    return jsonify({'error': 'Отчет не создан'}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)