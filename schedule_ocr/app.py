#!/usr/bin/env python3
"""
Schedule OCR Web App v0.1.1
Features: Robust JSON object detection, search fallback to OFF, persistent storage, time mapping.
"""

import os
import uuid
import base64
import json
import requests
import logging
import re
from flask import Flask, request, send_file, jsonify, render_template_string

# Setup logging
LOG_FILE = '/home/alice/.openclaw/workspace/schedule_ocr/access.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

app = Flask(__name__)
BASE_DIR = '/home/alice/.openclaw/workspace/schedule_ocr'
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(BASE_DIR, 'outputs')
app.config['DATA_FOLDER'] = os.path.join(BASE_DIR, 'data')

for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'], app.config['DATA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

OLLAMA_API = 'http://localhost:11434/api/generate'
VISION_MODEL = 'gemini-3-flash-preview'

def map_time(time_str):
    time_str = str(time_str).strip()
    if time_str == '0-8':
        return "午夜12點到隔天早上8點 (大夜班)"
    if time_str == '8-16':
        return "早上8點到當天下午4點 (白班)"
    if time_str == '16-0':
        return "當天下午4點到當天凌晨0點 (小夜班)"
    return time_str

def save_parsed_data(image_id, data):
    # Apply time mapping before saving
    processed_data = {}
    for name, schedules in data.items():
        processed_data[name] = []
        for s in schedules:
            processed_data[name].append({
                "date": s.get("date", ""),
                "time": map_time(s.get("time", ""))
            })
    
    path = os.path.join(app.config['DATA_FOLDER'], f"{image_id}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

def load_parsed_data(image_id):
    path = os.path.join(app.config['DATA_FOLDER'], f"{image_id}.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>排班表辨識系統</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 20px; font-size: 24px; text-align: center; }
        .upload-area { border: 2px dashed #ddd; border-radius: 8px; padding: 30px; text-align: center; margin-bottom: 20px; transition: all 0.3s; cursor: pointer; }
        .upload-area:hover { border-color: #4CAF50; background: #f9fff9; }
        input[type="file"] { display: none; }
        .btn { background: #4CAF50; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; width: 100%; margin-top: 10px; }
        .btn:disabled { background: #ccc; }
        .search-box { margin-top: 20px; }
        .search-box input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; margin-bottom: 10px; }
        .result { margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px; display: none; }
        .result.show { display: block; }
        .schedule-item { padding: 8px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
        .date { font-weight: bold; color: #2196F3; }
        .time { color: #4CAF50; }
        .loading { text-align: center; padding: 20px; display: none; }
        .loading.show { display: block; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #4CAF50; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .version { position: fixed; bottom: 15px; right: 15px; background: #fff; padding: 8px 14px; border-radius: 8px; font-size: 13px; color: #666; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border: 1px solid #e0e0e0; font-weight: 500; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 排班表辨識系統</h1>
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <p>📸 點擊或拖曳排班表圖片</p>
            <input type="file" id="fileInput" accept="image/*">
            <img id="preview" style="max-width:100%; margin-top:10px; display:none;">
        </div>
        <button class="btn" id="uploadBtn" onclick="uploadImage()" disabled>🔍 開始辨識</button>
        <div class="loading" id="loading"><div class="spinner"></div><p>正在分析中...</p></div>
        <div class="search-box">
            <input type="text" id="searchName" placeholder="👤 輸入姓名（如：鄭淑華）">
            <button class="btn" style="background:#2196F3" onclick="searchSchedule()">搜尋班表</button>
        </div>
        <div class="result" id="result">
            <h3 id="resultTitle">📊 班表結果</h3>
            <div id="scheduleList"></div>
            <button class="btn" style="background:#FF9800" onclick="exportICS()">📅 導出行事曆 (.ics)</button>
        </div>
        <div class="version">v0.1.4</div>
    </div>
    <script>
        let currentImageId = localStorage.getItem('lastImageId');
        function handleFile(file) {
            document.getElementById('uploadBtn').disabled = false;
            const reader = new FileReader();
            reader.onload = (e) => { 
                const p = document.getElementById('preview');
                p.src = e.target.result; p.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
        document.getElementById('fileInput').onchange = (e) => handleFile(e.target.files[0]);
        async function uploadImage() {
            const file = document.getElementById('fileInput').files[0];
            const formData = new FormData(); formData.append('image', file);
            document.getElementById('loading').classList.add('show');
            const resp = await fetch('/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            document.getElementById('loading').classList.remove('show');
            if (data.success) { 
                currentImageId = data.image_id; 
                localStorage.setItem('lastImageId', currentImageId);
                alert('✅ 辨識完成！可輸入姓名搜尋');
            } else alert('❌ 失敗：' + data.error);
        }
        async function searchSchedule() {
            const name = document.getElementById('searchName').value.trim();
            if (!name || !currentImageId) return alert('請先上傳圖片');
            const resp = await fetch('/api/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ image_id: currentImageId, name: name })
            });
            const data = await resp.json();
            if (data.success) {
                document.getElementById('result').classList.add('show');
                const list = document.getElementById('scheduleList');
                list.innerHTML = data.schedules.map(s => `<div class="schedule-item"><span>${s.date}</span><span>${s.time}</span></div>`).join('');
                document.getElementById('result').dataset.schedules = JSON.stringify(data.schedules);
                document.getElementById('result').dataset.name = data.name;
            } else alert('❌ ' + data.error);
        }
        async function exportICS() {
            const name = document.getElementById('result').dataset.name;
            const schedules = JSON.parse(document.getElementById('result').dataset.schedules);
            const resp = await fetch('/api/export/ics', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: name, schedules: schedules })
            });
            const data = await resp.json();
            if (data.success) window.location.href = data.download_url;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('image')
    if not file: return jsonify({'success': False, 'error': 'No image'}), 400
    image_id = str(uuid.uuid4())
    path = os.path.join(app.config['UPLOAD_FOLDER'], f'{image_id}.jpg')
    file.save(path)
    
    try:
        with open(path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        
        prompt = """請精確辨識這張排班表。
1. 提取表格中的所有人名（務必包含 鄭淑華 等）。
2. 提取每個人在每個日期的班次。
請用**純 JSON 格式**回答：{"schedules": {"姓名": [{"date": "115/03/09", "time": "時段"}, ...], ...}}"""
        
        resp = requests.post(OLLAMA_API, json={'model': VISION_MODEL, 'prompt': prompt, 'images': [img_data], 'stream': False}, timeout=120)
        
        # Log status and content-type
        logger.info(f"Ollama response status: {resp.status_code}")
        
        # Correctly parse the JSON response from Ollama generate API
        try:
            ollama_data = resp.json()
            raw_text = ollama_data.get('response', '').strip()
        except Exception as je:
            # Fallback if the body itself is not JSON or has extra data
            logger.warning(f"Failed to parse Ollama response as JSON: {je}")
            # Try to manually extract JSON from the body if it's a stream-like text
            body_text = resp.text
            match = re.search(r'\{.*\}', body_text, re.DOTALL)
            if match:
                raw_text = json.loads(match.group(0)).get('response', '').strip()
            else:
                raise ValueError("Could not extract response from Ollama body")

        logger.info(f"Raw AI for {image_id}: {raw_text[:300]}")

        # Brute-force JSON extraction v0.1.2
        try:
            # Look for the last JSON block if multiple exist, or first
            # Improved extraction to handle 'Extra data' errors
            all_json_blocks = []
            depth = 0
            start_idx = -1
            
            for i, char in enumerate(raw_text):
                if char == '{':
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        all_json_blocks.append(raw_text[start_idx:i+1])
                        start_idx = -1

            if not all_json_blocks:
                raise ValueError("No JSON block found")
            
            # Use the block that looks most like our schema
            json_str = ""
            for block in all_json_blocks:
                if '"schedules"' in block:
                    json_str = block
                    break
            
            if not json_str:
                json_str = all_json_blocks[0]

            # Pre-processing json_str to handle internal newlines and bad spacing
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            
            data = json.loads(json_str)
            save_parsed_data(image_id, data.get('schedules', {}))
            return jsonify({'success': True, 'image_id': image_id})
        except Exception as e:
            logger.error(f"Extraction failed: {e}. Raw: {raw_text}")
            return jsonify({'success': False, 'error': f'辨識解析錯誤：{str(e)}'})
            
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    req = request.json
    image_id, name = req.get('image_id'), req.get('name', '').strip()
    data = load_parsed_data(image_id) or {}
    
    # Fuzzy match
    for k, v in data.items():
        if name in k or k in name:
            return jsonify({'success': True, 'name': k, 'schedules': v})
    
    # Default to OFF if not found
    dummy_schedules = [{"date": "預設日期", "time": "休假 (辨識未匹配)"}]
    return jsonify({'success': True, 'name': f"{name} (預設)", 'schedules': dummy_schedules})

@app.route('/api/export/ics', methods=['POST'])
def export_ics():
    data = request.json
    name, schedules = data.get('name'), data.get('schedules', [])
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//OpenClaw//ScheduleOCR//TW\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\n"
    
    for s in schedules:
        time_text = s.get('time', '')
        # Skip off days
        if any(word in time_text for word in ['休', '例', '假', '贈']):
            continue
            
        try:
            # Parse date (Format expected: "115/03/09" or similar)
            d_parts = s['date'].split('/')
            year = int(d_parts[0]) + 1911 if len(d_parts[0]) == 3 else int(d_parts[0])
            month = int(d_parts[1])
            day = int(d_parts[2])
            
            # Determine Start/End times based on text
            start_time = "090000"
            end_time = "170000"
            
            if "大夜班" in time_text or "00-08" in time_text or "0-8" in time_text:
                start_time = "000000"
                end_time = "080000"
            elif "白班" in time_text or "08-16" in time_text or "8-16" in time_text:
                start_time = "080000"
                end_time = "160000"
            elif "小夜班" in time_text or "16-0" in time_text or "16-00" in time_text:
                start_time = "160000"
                end_time = "235959" # End of day
            
            dt_start = f"{year}{month:02d}{day:02d}T{start_time}"
            dt_end = f"{year}{month:02d}{day:02d}T{end_time}"
            
            # Handle special case: Big Night (00-08) usually refers to starting at midnight
            # If the user means 00-08 of that date, we use that date.
            
            ics += "BEGIN:VEVENT\n"
            ics += f"SUMMARY:{name} 上班 ({time_text})\n"
            ics += f"DTSTART;TZID=Asia/Taipei:{dt_start}\n"
            ics += f"DTEND;TZID=Asia/Taipei:{dt_end}\n"
            ics += f"DESCRIPTION:辨識班次: {time_text}\n"
            ics += "END:VEVENT\n"
        except Exception as e:
            logger.error(f"ICS export error for {s}: {e}")
            continue
            
    ics += "END:VCALENDAR"
    fn = f"{name}_schedule.ics"
    with open(os.path.join(app.config['OUTPUT_FOLDER'], fn), 'w', encoding='utf-8') as f: 
        f.write(ics)
    return jsonify({'success': True, 'download_url': f'/download/{fn}'})

@app.route('/download/<filename>')
def download(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
