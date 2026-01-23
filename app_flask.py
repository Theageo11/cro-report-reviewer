"""
明捷医药报告审核 Demo - Flask Web 应用
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from src.database import Database
from src.parser import DocxParser
from src.llm import QwenClient
from src.commenter import generate_commented_docx
import json
from bs4 import BeautifulSoup
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB
app.config['UPLOAD_FOLDER'] = 'temp_docs'
app.secret_key = 'your-secret-key-here'  # 在生产环境中应该使用环境变量

# 确保上传目录存在
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# 初始化数据库
db = Database()

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def highlight_text(html_content, issues, active_id=None):
    """高亮显示文档中的问题位置"""
    if not issues:
        return html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for i, issue in enumerate(issues):
        try:
            category = issue.get("category", "text")
            eid = int(issue.get("element_id", -1))
            text_to_highlight = issue.get("original_text", "").strip()
            
            color = "#fef3c7"  # Default Major (Yellow)
            border_color = "#f59e0b"
            if issue["issue_type"] == "Critical":
                color = "#fee2e2"  # Red
                border_color = "#ef4444"
            elif issue["issue_type"] == "Minor":
                color = "#e0f2fe"  # Blue
                border_color = "#3b82f6"
            
            is_active = (active_id == i)
            anchor_id = f"issue-{i}"
            
            if category == "image" and eid != -1:
                target_tag = soup.find(id=f"doc-el-{eid}")
                if target_tag:
                    target_tag['id'] = anchor_id
                    active_style = "outline: 5px solid #ef4444; outline-offset: 5px;" if is_active else f"outline: 3px solid {border_color};"
                    target_tag['style'] = target_tag.get('style', '') + f"; {active_style}"
            
            elif (category == "text" or category == "table") and text_to_highlight:
                found = False
                search_tags = []
                if eid != -1:
                    marker = soup.find(id=f"doc-el-{eid}")
                    if marker:
                        search_tags.append(marker.parent)
                
                if not search_tags:
                    search_tags = soup.find_all(['p', 'td', 'th', 'h1', 'h2', 'h3', 'li'])
                
                for tag in search_tags:
                    for text_node in tag.find_all(string=True):
                        if text_to_highlight in text_node:
                            active_style = "outline: 4px solid #ef4444; outline-offset: 2px; box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);" if is_active else ""
                            highlight_html = f'<span id="{anchor_id}" style="background-color: {color}; border-bottom: 2px solid {border_color}; font-weight: bold; {active_style}">{text_to_highlight}</span>'
                            new_content = text_node.replace(text_to_highlight, highlight_html)
                            new_soup = BeautifulSoup(new_content, 'html.parser')
                            text_node.replace_with(new_soup)
                            found = True
                            break
                    if found:
                        break
                
                if not found and eid != -1:
                    target_tag = soup.find(id=f"doc-el-{eid}")
                    if target_tag:
                        target_tag['id'] = anchor_id
                        active_style = "outline: 4px solid #ef4444; outline-offset: 2px;" if is_active else ""
                        target_tag['style'] = target_tag.get('style', '') + f"; background-color: {color}; border-left: 4px solid {border_color}; padding: 4px; {active_style}"
        except Exception:
            continue
    
    return str(soup)


@app.route('/')
def index():
    """重定向到文档页面"""
    return redirect(url_for('documents'))


@app.route('/documents')
def documents():
    """文档列表页面"""
    docs = db.get_all_documents()
    
    # 计算风险统计数据
    critical_count = sum(1 for d in docs if d.get('status') == 'analyzed' and d.get('critical_count', 0) > 0)
    major_count = sum(1 for d in docs if d.get('status') == 'analyzed' and d.get('major_count', 0) > 0)
    analyzed_count = sum(1 for d in docs if d.get('status') == 'analyzed')
    low_count = analyzed_count - critical_count - major_count
    
    risk_stats = {
        'high': critical_count,
        'medium': major_count,
        'low': low_count if low_count > 0 else 0
    }
    
    return render_template('documents.html', documents=docs, risk_stats=risk_stats)


@app.route('/documents/<doc_id>')
def document_detail(doc_id):
    """文档详情页面"""
    doc = db.get_document(doc_id)
    if not doc:
        return "文档不存在", 404
    
    # 解析文档HTML
    html_content = ""
    if doc['status'] in ['analyzed', 'analyzing']:
        parser = DocxParser()
        doc_data = parser.get_content_and_html(doc['file_path'])
        html_content = doc_data['html']
        
        # 如果有分析结果，高亮显示
        if doc['status'] == 'analyzed' and doc.get('issues'):
            html_content = highlight_text(html_content, doc['issues'])
    
    # 计算风险统计数据（用于侧边栏）
    docs = db.get_all_documents()
    critical_count = sum(1 for d in docs if d.get('status') == 'analyzed' and d.get('critical_count', 0) > 0)
    major_count = sum(1 for d in docs if d.get('status') == 'analyzed' and d.get('major_count', 0) > 0)
    analyzed_count = sum(1 for d in docs if d.get('status') == 'analyzed')
    low_count = analyzed_count - critical_count - major_count
    
    risk_stats = {
        'high': critical_count,
        'medium': major_count,
        'low': low_count if low_count > 0 else 0
    }
    
    return render_template('document_detail.html', document=doc, html_content=html_content, risk_stats=risk_stats)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传文档"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 生成唯一文件名
        import uuid
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # 创建数据库记录
        doc_id = db.create_document(unique_filename, filename, filepath)
        
        return jsonify({
            'success': True,
            'doc_id': doc_id,
            'message': '上传成功'
        })
    
    return jsonify({'error': '不支持的文件类型'}), 400


@app.route('/api/analyze/<doc_id>', methods=['POST'])
def analyze_document(doc_id):
    """分析文档"""
    doc = db.get_document(doc_id)
    if not doc:
        return jsonify({'error': '文档不存在'}), 404
    
    # 更新状态为分析中
    db.update_document(doc_id, {'status': 'analyzing'})
    
    try:
        # 解析文档
        parser = DocxParser()
        doc_data = parser.get_content_and_html(doc['file_path'])
        
        # 调用 LLM 分析
        use_mock = request.json.get('use_mock', False) if request.json else False
        
        if use_mock and os.path.exists("mock_analysis_result.json"):
            with open("mock_analysis_result.json", "r", encoding="utf-8") as f:
                issues = json.load(f)
        else:
            llm_client = QwenClient()
            issues = llm_client.analyze_report(doc_data['content'])
            
            # 保存 mock 结果
            try:
                with open("mock_analysis_result.json", "w", encoding="utf-8") as f:
                    json.dump(issues, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        
        # 更新分析结果
        db.update_analysis(doc_id, issues, doc_data['content'])
        
        return jsonify({
            'success': True,
            'message': '分析完成',
            'issues_count': len(issues)
        })
    
    except Exception as e:
        db.update_document(doc_id, {'status': 'uploaded'})
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档"""
    if db.delete_document(doc_id):
        return jsonify({'success': True, 'message': '删除成功'})
    return jsonify({'error': '文档不存在'}), 404


@app.route('/api/download/<doc_id>')
def download_document(doc_id):
    """下载带批注的文档"""
    doc = db.get_document(doc_id)
    if not doc:
        return jsonify({'error': '文档不存在'}), 404
    
    if doc['status'] != 'analyzed':
        return jsonify({'error': '文档尚未分析'}), 400
    
    # 生成带批注的文档
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"commented_{doc['original_filename']}")
    
    try:
        generate_commented_docx(doc['file_path'], output_path, doc['issues'])
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"审核版_{doc['original_filename']}",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/quality')
def quality():
    """质量研究页面（占位）"""
    return render_template('placeholder.html', page_name='质量研究')


@app.route('/analysis')
def analysis():
    """数据分析页面（占位）"""
    return render_template('placeholder.html', page_name='数据分析')


@app.route('/reports')
def reports():
    """检测报告页面（占位）"""
    return render_template('placeholder.html', page_name='检测报告')


@app.route('/settings')
def settings():
    """Settings 页面（占位）"""
    return render_template('placeholder.html', page_name='设置')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

