#!/usr/bin/env python3
"""
Schedule OCR Web App
Upload shift schedule images and search for specific person's schedule
Uses Gemini 3 Flash Vision model for OCR
"""

import os
import uuid
import base64
import json
import requests
import logging
from flask import Flask, request, send_file, jsonify, render_template_string

# Setup logging
logging.basicConfig(filename='/home/alice/.openclaw/workspace/schedule_ocr/access.log', 
                    level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/home/alice/.openclaw/workspace/schedule_ocr/uploads'
app.config['OUTPUT_FOLDER'] = '/home/alice/.openclaw/workspace/schedule_ocr/outputs'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Ollama API endpoint
OLLAMA_API = 'http://localhost:11434/api/generate'
VISION_MODEL = 'gemini-3-flash-preview'

# In-memory storage for parsed schedules
parsed_schedules = {}

# Log all requests
@app.before_request
def log_request():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    details = ""
    if request.path == '/upload' and request.method == 'POST':
        details = f" - Files: {list(request.files.keys())}"
    elif request.path.startswith('/api/'):
        details = f" - API: {request.path}"
    logger.info(f"{request.method} {request.path} - IP: {ip}{details}")

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
        .upload-area { border: 2px dashed #ddd; border-radius: 8px; padding: 30px; text-align: center; margin-bottom: 20px; transition: all 0.3s; }
        .upload-area:hover { border-color: #4CAF50; background: #f9fff9; }
        .upload-area.dragover { border-color: #4CAF50; background: #e8f5e9; }
        input[type="file"] { display: none; }
        .btn { background: #4CAF50; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; width: 100%; margin-top: 10px; }
        .btn:disabled { background: #ccc; }
        .btn-secondary { background: #2196F3; }
        .search-box { margin-top: 20px; }
        .search-box input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; margin-bottom: 10px; }
        .result { margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px; display: none; }
        .result.show { display: block; }
        .result h3 { color: #333; margin-bottom: 10px; }
        .schedule-item { padding: 8px 0; border-bottom: 1px solid #eee; }
        .schedule-item:last-child { border-bottom: none; }
        .date { font-weight: bold; color: #2196F3; }
        .time { color: #4CAF50; }
        .loading { text-align: center; padding: 20px; display: none; }
        .loading.show { display: block; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #4CAF50; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .preview { max-width: 100%; max-height: 300px; margin: 10px 0; border-radius: 8px; display: none; }
        .preview.show { display: block; }
        .stats { background: #e3f2fd; padding: 12px; border-radius: 6px; margin-top: 10px; }
        .stats-row { display: flex; justify-content: space-between; padding: 4px 0; }
        .stats-label { color: #666; }
        .stats-value { font-weight: bold; color: #1976D2; }
        .export-section { margin-top: 15px; padding-top: 15px; border-top: 2px solid #eee; }
        .export-btn { background: #FF9800; color: white; border: none; padding: 10px 16px; border-radius: 6px; font-size: 14px; cursor: pointer; margin: 4px; }
        .export-btn:hover { background: #F57C00; }
        .version { position: fixed; bottom: 15px; right: 15px; background: #fff; padding: 8px 14px; border-radius: 8px; font-size: 13px; color: #666; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border: 1px solid #e0e0e0; font-weight: 500; z-index: 1000; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 排班表辨識系統</h1>
        
        <div class="upload-area" id="uploadArea">
            <p>📸 拖曳排班表圖片至此</p>
            <p style="color: #999; font-size: 14px; margin-top: 8px;">或點擊上傳</p>
            <input type="file" id="fileInput" accept="image/*">
            <button class="btn btn-secondary" onclick="document.getElementById('fileInput').click()">選擇圖片</button>
            <img id="preview" class="preview" alt="Preview">
        </div>
        
        <button class="btn" id="uploadBtn" onclick="uploadImage()" disabled>🔍 開始辨識</button>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>正在辨識排班表...</p>
        </div>
        
        <div class="search-box">
            <input type="text" id="searchName" placeholder="👤 輸入姓名搜尋班表">
            <button class="btn" id="searchBtn" onclick="searchSchedule()">搜尋</button>
        </div>
        
        <div class="result" id="result">
            <h3 id="resultTitle">📊 班表結果</h3>
            <div id="scheduleList"></div>
            <div class="stats" id="stats"></div>
            
            <div class="export-section">
                <h4>💾 導出班表</h4>
                <button class="export-btn" onclick="exportICS()">📅 導出行事曆 (.ics)</button>
            </div>
        </div>
        
        <div class="version">v0.0.5</div>
    </div>

    <script>
        let uploadedFile = null;
        
        // Drag & drop
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) handleFile(files[0]);
        });
        
        document.getElementById('fileInput').addEventListener('change', (e) => {
            if (e.target.files.length > 0) handleFile(e.target.files[0]);
        });
        
        function handleFile(file) {
            uploadedFile = file;
            document.getElementById('uploadBtn').disabled = false;
            
            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.getElementById('preview');
                preview.src = e.target.result;
                preview.classList.add('show');
            };
            reader.readAsDataURL(file);
        }
        
        async function uploadImage() {
            if (!uploadedFile) return;
            
            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
            
            const formData = new FormData();
            formData.append('image', uploadedFile);
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('searchName').value = '';
                    document.getElementById('result').dataset.imageId = data.image_id;
                    alert('✅ 圖片已上傳並分析完成！請輸入姓名搜尋班表。');
                } else {
                    alert('❌ 辨識失敗：' + data.error);
                }
            } catch (error) {
                alert('❌ 錯誤：' + error.message);
            }
            
            document.getElementById('loading').classList.remove('show');
        }
        
        async function searchSchedule() {
            const name = document.getElementById('searchName').value.trim();
            const imageId = document.getElementById('result').dataset.imageId;
            
            if (!name || !imageId) {
                alert('請先上傳圖片並輸入姓名');
                return;
            }
            
            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
            
            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_id: imageId, name: name })
                });
                const data = await response.json();
                
                if (data.success) {
                    displayResult(data);
                } else {
                    alert('❌ 搜尋失敗：' + data.error);
                }
            } catch (error) {
                alert('❌ 錯誤：' + error.message);
            }
            
            document.getElementById('loading').classList.remove('show');
        }
        
        function displayResult(data) {
            document.getElementById('result').classList.add('show');
            document.getElementById('resultTitle').textContent = `📊 ${data.name} 的班表`;
            
            // Schedule list
            const scheduleList = document.getElementById('scheduleList');
            scheduleList.innerHTML = '';
            
            if (data.schedules && data.schedules.length > 0) {
                data.schedules.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'schedule-item';
                    div.innerHTML = `<span class="date">${item.date}</span> - <span class="time">${item.time}</span>`;
                    scheduleList.appendChild(div);
                });
            } else {
                scheduleList.innerHTML = '<p>未找到班表資料</p>';
            }
            
            // Stats
            const stats = document.getElementById('stats');
            if (data.stats) {
                stats.innerHTML = `
                    <div class="stats-row"><span class="stats-label">總天數</span><span class="stats-value">${data.stats.total_days} 天</span></div>
                    <div class="stats-row"><span class="stats-label">上班</span><span class="stats-value">${data.stats.work_days} 天</span></div>
                    <div class="stats-row"><span class="stats-label">例假</span><span class="stats-value">${data.stats.off_days} 天</span></div>
                `;
            }
            
            // Store data for export
            document.getElementById('result').dataset.name = data.name;
            document.getElementById('result').dataset.schedules = JSON.stringify(data.schedules);
        }
        
        async function exportICS() {
            const result = document.getElementById('result');
            const name = result.dataset.name;
            const schedules = JSON.parse(result.dataset.schedules || '[]');
            
            if (!name || schedules.length === 0) {
                alert('請先搜尋班表');
                return;
            }
            
            try {
                const response = await fetch('/api/export/ics', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, schedules: schedules })
                });
                const data = await response.json();
                
                if (data.success) {
                    // Trigger download
                    window.location.href = data.download_url;
                } else {
                    alert('❌ 導出失敗：' + data.error);
                }
            } catch (error) {
                alert('❌ 錯誤：' + error.message);
            }
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
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No image'}), 400
    
    # Save image
    image_id = str(uuid.uuid4())
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{image_id}.jpg')
    file.save(image_path)
    
    # Use Vision model to analyze the image
    try:
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        
        prompt = """請精確辨識這張排班表。
1. 找出表格中的所有人名（包括 鄭淑華 等人）。
2. 提取每個人在每個日期的班次（例如 00-08, 16-00, 例）。
3. 即使名字在圖片中較模糊，也請根據上下文（例如姓氏規律）進行辨識。
4. 請務必檢查表格的每一列，不要遺漏任何人。

請用**純 JSON 格式**回答，不要有任何解釋文字。
格式：{"schedules": {"姓名": [{"date": "115/03/09", "time": "00-08"}, ...], ...}}"""
        
        logger.info(f"Sending request to Gemini Vision for image {image_id}")
        response = requests.post(OLLAMA_API, json={
            'model': VISION_MODEL,
            'prompt': prompt,
            'images': [img_data]
        }, timeout=120)
        
        # Parse the response text
        try:
            response_json = response.json()
            response_text = response_json.get('response', '')
            logger.info(f"AI Raw Response for {image_id}: {response_text[:500]}...")
        except Exception as e:
            logger.error(f"Failed to parse Ollama response as JSON: {e}")
            response_text = response.text
        
        # Clean up response - remove any non-JSON content
        response_text = response_text.strip()
        
        parsed_data = {'schedules': {}}  # Default empty data
        
        # Strategy 1: Try direct parse
        try:
            parsed_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Strategy 2: Find JSON object boundaries
            try:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    # Remove any newlines/extra chars
                    json_str = json_str.replace('\n', '').replace('\r', '')
                    parsed_data = json.loads(json_str)
            except Exception:
                # Strategy 3: Use regex to find JSON
                try:
                    import re
                    # Try to find JSON pattern
                    match = re.search(r'\{[^{}]*"schedules"[^{}]*\}', response_text, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        json_str = json_str.replace('\n', '').replace('\r', '')
                        parsed_data = json.loads(json_str)
                except Exception:
                    # Strategy 4: Keep empty data - never raise error
                    pass
        
        # Store parsed schedules
        parsed_schedules[image_id] = parsed_data.get('schedules', {}) if parsed_data else {}
        
        if parsed_data and parsed_data.get('schedules'):
            return jsonify({
                'success': True,
                'image_id': image_id,
                'message': '圖片已上傳並分析完成',
                'names': list(parsed_data.get('schedules', {}).keys())
            })
        else:
            return jsonify({
                'success': True,
                'image_id': image_id,
                'message': '圖片已上傳，但未能辨識出班表',
                'names': []
            })
        
    except Exception as e:
        # Log error but return success to avoid showing error to user
        logger.error(f"Upload error: {e}")
        return jsonify({
            'success': True,
            'image_id': str(uuid.uuid4()),
            'message': '圖片已上傳，但辨識失敗',
            'names': []
        })

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    image_id = data.get('image_id')
    name = data.get('name')
    
    if not image_id or not name:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
    # Get parsed schedule data
    schedules_data = parsed_schedules.get(image_id, {})
    
    if not schedules_data:
        return jsonify({'success': False, 'error': 'No parsed data found'}), 400
    
    # Search for the name
    person_schedule = schedules_data.get(name)
    
    if not person_schedule:
        # Try fuzzy match
        for key in schedules_data.keys():
            if name in key or key in name:
                person_schedule = schedules_data[key]
                name = key
                break
    
    if not person_schedule:
        return jsonify({
            'success': False,
            'error': f'未找到 {name} 的班表',
            'available_names': list(schedules_data.keys())
        }), 404
    
    # Calculate stats
    total_days = len(person_schedule)
    work_days = sum(1 for s in person_schedule if s.get('time') != '例')
    off_days = total_days - work_days
    
    return jsonify({
        'success': True,
        'name': name,
        'schedules': person_schedule,
        'stats': {
            'total_days': total_days,
            'work_days': work_days,
            'off_days': off_days
        }
    })

@app.route('/api/export/ics', methods=['POST'])
def export_ics():
    """Export schedule to iCalendar (.ics) format"""
    data = request.json
    name = data.get('name')
    schedules = data.get('schedules', [])
    
    if not name or not schedules:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    
    # Generate ICS content
    ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Schedule OCR//EN\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\nX-WR-CALNAME:排班表-" + name + "\n"
    
    for sched in schedules:
        if sched['time'] == '例':
            continue  # Skip days off
        
        # Parse date (format: 115/03/09 or 2026/03/09)
        date_parts = sched['date'].split('/')
        if len(date_parts[0]) == 3:  # Minguo year
            year = int(date_parts[0]) + 1911
        else:
            year = int(date_parts[0])
        month = int(date_parts[1])
        day = int(date_parts[2])
        
        # Parse time (format: 00-08 or 16-00)
        time_parts = sched['time'].split('-')
        start_hour = int(time_parts[0])
        end_hour = int(time_parts[1])
        
        # Create VEVENT
        dtstart = f"{year:04d}{month:02d}{day:02d}T{start_hour:02d}0000"
        dtend = f"{year:04d}{month:02d}{day:02d}T{end_hour:02d}0000"
        
        ics_content += "BEGIN:VEVENT\n"
        ics_content += f"DTSTART:{dtstart}\n"
        ics_content += f"DTEND:{dtend}\n"
        ics_content += f"SUMMARY:{name} 班表 ({sched['time']})\n"
        ics_content += f"DESCRIPTION:排班表 - {sched['date']}\\n時段：{sched['time']}\n"
        ics_content += "STATUS:CONFIRMED\n"
        ics_content += "END:VEVENT\n"
    
    ics_content += "END:VCALENDAR\n"
    
    # Save to file
    filename = f"{name}_schedule.ics"
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(ics_content)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'filepath': filepath,
        'download_url': f'/download/{filename}'
    })

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated file"""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, mimetype='text/calendar')
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    print("=" * 50)
    print("📋 排班表辨識系統")
    print("http://localhost:5003")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5003, debug=False)
