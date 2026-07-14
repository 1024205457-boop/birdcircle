"""
BirdCircle 后端服务
Flask + SQLite，端口 8001
功能：鸟讯提交/获取、打卡、照片上传
"""

import os
import uuid
import sqlite3
import time
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ===== 配置 =====
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'birdcircle.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE

# ===== 数据库初始化 =====
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            bird_name TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            spot_name TEXT DEFAULT '',
            lat REAL DEFAULT 0,
            lng REAL DEFAULT 0,
            photo_path TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            spot_name TEXT NOT NULL,
            lat REAL DEFAULT 0,
            lng REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_reports_device ON reports(device_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_checkins_device ON checkins(device_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_checkins_spot_date ON checkins(spot_name, created_at)")
    conn.commit()
    conn.close()

init_db()

# ===== 工具函数 =====
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_streak(device_id):
    """计算连续打卡天数"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT date(created_at) as d
        FROM checkins
        WHERE device_id = ?
        ORDER BY d DESC
    """, (device_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return 0
    streak = 1
    today_str = str(date.today())
    if rows[0]['d'] != today_str:
        # 今天没打卡，检查昨天
        from datetime import timedelta
        yesterday_str = str(date.today() - timedelta(days=1))
        if rows[0]['d'] != yesterday_str:
            return 0
    for i in range(len(rows) - 1):
        from datetime import timedelta
        d1 = datetime.strptime(rows[i]['d'], '%Y-%m-%d').date()
        d2 = datetime.strptime(rows[i + 1]['d'], '%Y-%m-%d').date()
        if (d1 - d2).days == 1:
            streak += 1
        else:
            break
    return streak

# ===== API 路由 =====

# ---------- 鸟讯 ----------
@app.route('/api/report', methods=['POST'])
def submit_report():
    """提交鸟讯"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'no data'}), 400

        device_id = data.get('device_id', '')[:100]
        bird_name = data.get('bird_name', '未知鸟种')[:50]
        confidence = float(data.get('confidence', 0))
        spot_name = data.get('spot_name', '')[:100]
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
        description = data.get('description', '')[:500]

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO reports (device_id, bird_name, confidence, spot_name, lat, lng, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (device_id, bird_name, confidence, spot_name, lat, lng, description))
        report_id = c.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'ok': True, 'id': report_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/<int:report_id>/photo', methods=['POST'])
def upload_report_photo(report_id):
    """为鸟讯上传照片"""
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'no photo'}), 400
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'error': 'empty filename'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'invalid file type'}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"report_{report_id}_{int(time.time())}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE reports SET photo_path = ? WHERE id = ?", (f"uploads/{filename}", report_id))
        conn.commit()
        conn.close()

        return jsonify({'ok': True, 'photo_path': f"uploads/{filename}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
def get_reports():
    """获取鸟讯列表（支持分页和按地点筛选）"""
    try:
        spot = request.args.get('spot', '')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = max(int(request.args.get('offset', 0)), 0)

        conn = get_db()
        c = conn.cursor()
        if spot:
            c.execute("""
                SELECT id, device_id, bird_name, confidence, spot_name, lat, lng,
                       photo_path, description, created_at
                FROM reports
                WHERE spot_name LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (f'%{spot}%', limit, offset))
        else:
            c.execute("""
                SELECT id, device_id, bird_name, confidence, spot_name, lat, lng,
                       photo_path, description, created_at
                FROM reports
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        rows = c.fetchall()
        conn.close()

        reports = []
        for r in rows:
            reports.append({
                'id': r['id'],
                'device_id': r['device_id'],
                'bird_name': r['bird_name'],
                'confidence': r['confidence'],
                'spot_name': r['spot_name'],
                'lat': r['lat'],
                'lng': r['lng'],
                'photo_path': r['photo_path'],
                'description': r['description'],
                'created_at': r['created_at']
            })
        return jsonify({'ok': True, 'data': reports, 'total': len(reports)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- 打卡 ----------
@app.route('/api/checkin', methods=['POST'])
def checkin():
    """鸟点打卡"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'no data'}), 400

        device_id = data.get('device_id', '')[:100]
        spot_name = data.get('spot_name', '')[:100]
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))

        # 检查今天是否已打卡该地点
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT id FROM checkins
            WHERE device_id = ? AND spot_name = ? AND date(created_at) = date('now','localtime')
        """, (device_id, spot_name))
        if c.fetchone():
            conn.close()
            return jsonify({'ok': True, 'msg': '今天已打卡', 'already': True})

        c.execute("""
            INSERT INTO checkins (device_id, spot_name, lat, lng)
            VALUES (?, ?, ?, ?)
        """, (device_id, spot_name, lat, lng))
        conn.commit()
        conn.close()

        streak = get_streak(device_id)
        points = 5  # 每次打卡+5
        return jsonify({'ok': True, 'msg': '打卡成功', 'already': False,
                        'points': points, 'streak': streak})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/checkin/streak', methods=['GET'])
def get_checkin_streak():
    """获取连续打卡天数"""
    try:
        device_id = request.args.get('device_id', '')[:100]
        streak = get_streak(device_id)
        return jsonify({'ok': True, 'streak': streak})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- 上传的静态文件 ----------
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """serve 上传的照片"""
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- 健康检查 ----------
@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'db': 'connected'})

# ===== 启动 =====
if __name__ == '__main__':
    print("BirdCircle 后端启动中...")
    print(f"数据库: {DB_PATH}")
    print(f"上传目录: {UPLOAD_FOLDER}")
    app.run(host='0.0.0.0', port=8001, debug=False)
