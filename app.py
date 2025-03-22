import os
import uuid
import time
import json
import builtins
import shutil
import zipfile
from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from flask_cors import CORS
import subprocess
from werkzeug.utils import secure_filename
from industry_report_generator import generate_report, ReportConfig, IndustryReportGenerator

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

# 全局进度变量
progress = {"message": "初始化中...", "percentage": 0}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'json', 'md', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_zip_archive(task_id, report_dir):
    """创建包含所有文件的ZIP压缩包"""
    zip_path = os.path.join(REPORT_FOLDER, f"{task_id}_complete.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加所有文件到压缩包
        for root, dirs, files in os.walk(report_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, report_dir)
                zipf.write(file_path, arcname)
    return zip_path

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')  # 从当前目录提供index.html

@app.route('/api/generate-report', methods=['POST'])
def api_generate_report():
    # 检查是否有文件和必要的参数
    if 'industry' not in request.form:
        return jsonify({'error': 'Missing industry parameter'}), 400
    
    if 'zhipu_api_key' not in request.form:
        return jsonify({'error': 'Missing Zhipu API key'}), 400
        
    if 'deepseek_api_key' not in request.form:
        return jsonify({'error': 'Missing DeepSeek API key'}), 400
    
    industry = request.form['industry']
    zhipu_api_key = request.form['zhipu_api_key']
    deepseek_api_key = request.form['deepseek_api_key']
    current_industry = request.form.get('current_industry', '')
    output_format = request.form.get('output_format', 'markdown')  # 默认为markdown
    
    # 生成唯一的任务ID
    task_id = str(uuid.uuid4())
    output_dir = os.path.join(REPORT_FOLDER, task_id)
    
    # 处理模板文件上传
    template_path = None
    if 'template' in request.files:
        template_file = request.files['template']
        if template_file and allowed_file(template_file.filename):
            filename = secure_filename(template_file.filename)
            template_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
            template_file.save(template_path)
    
    # 创建进度跟踪变量
    global progress
    progress = {"message": "初始化中...", "percentage": 0}
    
    # 定义进度回调函数
    def progress_callback(message, percentage):
        global progress
        progress["message"] = message
        progress["percentage"] = percentage
    
    # 在后台线程中运行报告生成
    def generate_report_task():
        try:
            # 设置环境变量，供各步骤使用
            os.environ["ZHIPU_API_KEY"] = zhipu_api_key
            os.environ["DS_API_KEY"] = deepseek_api_key
            
            # 确保所有步骤使用相同的输出目录
            task_output_dir = os.path.join(REPORT_FOLDER, task_id)
            step0_dir = os.path.join(task_output_dir, "step0")
            step1_dir = os.path.join(task_output_dir, "step1")
            step2_dir = os.path.join(task_output_dir, "step2")
            final_dir = os.path.join(task_output_dir, "final")
            
            # 创建必要的目录
            os.makedirs(step0_dir, exist_ok=True)
            os.makedirs(step1_dir, exist_ok=True)
            os.makedirs(step2_dir, exist_ok=True)
            os.makedirs(final_dir, exist_ok=True)
            
            # 如果有模板文件，复制到step0目录
            local_template_path = template_path  # 使用局部变量引用外部变量
            if local_template_path:
                template_filename = os.path.basename(local_template_path)
                step0_template_path = os.path.join(step0_dir, template_filename)
                shutil.copy2(local_template_path, step0_template_path)
                local_template_path = step0_template_path
            
            result = generate_report(
                industry=industry,
                api_key=deepseek_api_key,  # 主要使用DeepSeek API
                zhipu_api_key=zhipu_api_key,  # 额外传递智谱API
                output_dir=task_output_dir,
                template_path=local_template_path,
                current_industry=current_industry,
                callback=progress_callback,
                output_format=output_format  # 传递输出格式参数
            )
            
            # 如果需要PDF格式，使用pandoc转换
            if output_format == 'pdf' and result["success"]:
                md_path = result["output_files"]["final_report"]
                pdf_path = md_path.replace('.md', '.pdf')
                
                try:
                    # 获取最终报告所在目录
                    report_dir = os.path.dirname(md_path)
                    
                    # 确保charts目录存在
                    charts_dir = os.path.join(report_dir, "charts")
                    if not os.path.exists(charts_dir):
                        print(f"警告: 图表目录不存在: {charts_dir}")
                    
                    print(f"正在将Markdown转换为PDF: {md_path} -> {pdf_path}")
                    
                    # 使用pandoc转换为PDF，添加更多参数以优化输出
                    pandoc_cmd = [
                        "pandoc", 
                        md_path, 
                        "-o", pdf_path,
                        "--pdf-engine=xelatex",
                        "-V", "mainfont=SimSun",  # 使用中文字体
                        "-V", "geometry:margin=1in",  # 设置页边距
                        "-V", "colorlinks=true",  # 彩色链接
                        "-V", "linkcolor=blue",  # 链接颜色
                        "-V", "toccolor=blue",  # 目录链接颜色
                        "-V", "urlcolor=blue",  # URL颜色
                        "--toc",  # 添加目录
                        "--standalone",
                        "--highlight-style=tango"  # 代码高亮风格
                    ]
                    
                    # 执行pandoc命令
                    process = subprocess.run(
                        pandoc_cmd,
                        capture_output=True,
                        text=True
                    )
                    
                    if process.returncode != 0:
                        print(f"PDF转换失败: {process.stderr}")
                    elif os.path.exists(pdf_path):
                        print(f"PDF转换成功: {pdf_path}")
                        result["output_files"]["final_report_pdf"] = pdf_path
                    else:
                        print(f"PDF文件未生成: {pdf_path}")
                except Exception as e:
                    print(f"PDF转换过程中出错: {str(e)}")
                    # 继续执行，不因PDF转换失败而中断整个流程
            
            # 查找并添加自包含版Markdown文件
            if result["success"]:
                self_contained_file = os.path.join(final_dir, f"{industry}行业调研报告_自包含版.md")
                if os.path.exists(self_contained_file):
                    result["output_files"]["self_contained_report"] = self_contained_file
                    print(f"已找到并添加自包含版Markdown文件: {self_contained_file}")
                
                # 查找report_files.json中的信息
                report_info_path = os.path.join(final_dir, "report_files.json")
                if os.path.exists(report_info_path):
                    try:
                        with open(report_info_path, "r", encoding="utf-8") as f:
                            report_info = json.load(f)
                        
                        if "self_contained_report" in report_info and os.path.exists(report_info["self_contained_report"]):
                            result["output_files"]["self_contained_report"] = report_info["self_contained_report"]
                            print(f"从report_files.json中添加自包含报告文件: {report_info['self_contained_report']}")
                    except Exception as e:
                        print(f"读取report_files.json时出错: {str(e)}")
            
            # 创建完整压缩包
            if result["success"]:
                zip_path = create_zip_archive(task_id, task_output_dir)
                result["output_files"]["complete_zip"] = zip_path
            
            # 保存结果到文件
            with open(os.path.join(output_dir, "result.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "output_files": {},
                "execution_time": 0
            }
            # 保存错误结果
            with open(os.path.join(output_dir, "result.json"), "w", encoding="utf-8") as f:
                json.dump(error_result, f, ensure_ascii=False, indent=2)
            return error_result
    
    # 启动后台任务
    import threading
    thread = threading.Thread(target=generate_report_task)
    thread.daemon = True
    thread.start()
    
    # 返回任务ID，客户端可以用它来查询进度
    return jsonify({
        'task_id': task_id,
        'message': '报告生成任务已启动'
    })

@app.route('/api/report-progress/<task_id>', methods=['GET'])
def report_progress(task_id):
    # 检查任务是否完成
    result_path = os.path.join(REPORT_FOLDER, task_id, "result.json")
    if os.path.exists(result_path):
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                result = json.load(f)
            return jsonify({
                'status': 'completed',
                'result': result
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'读取结果文件出错: {str(e)}'
            })
    
    # 如果任务未完成，返回当前进度
    global progress
    return jsonify({
        'status': 'in_progress',
        'progress': progress
    })

@app.route('/api/download/<task_id>/<file_type>', methods=['GET'])
def download_report(task_id, file_type):
    # 检查任务是否存在
    task_dir = os.path.join(REPORT_FOLDER, task_id)
    if not os.path.exists(task_dir):
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查结果文件
    result_path = os.path.join(task_dir, "result.json")
    if not os.path.exists(result_path):
        return jsonify({'error': '报告尚未生成完成'}), 400
    
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        if not result["success"]:
            return jsonify({'error': f'报告生成失败: {result["error"]}'}), 400
        
        industry = result['industry']
        
        if file_type == 'markdown':
            file_path = result["output_files"]["final_report"]
            return send_file(file_path, as_attachment=True, download_name=f"{industry}行业调研报告.md")
        elif file_type == 'self_contained':
            # 首先尝试从result.json中获取路径
            file_path = result["output_files"].get("self_contained_report")
            
            # 如果不存在，尝试寻找可能的路径
            if not file_path or not os.path.exists(file_path):
                # 尝试寻找常见的自包含报告文件名格式
                final_dir = os.path.join(task_dir, "final")
                possible_paths = [
                    os.path.join(final_dir, f"{industry}行业调研报告_自包含版.md"),
                    os.path.join(final_dir, f"{industry}行业调研报告_内联版.md"),
                    os.path.join(final_dir, f"{industry}行业调研报告_base64版.md")
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        file_path = path
                        # 更新result中的路径以便将来使用
                        result["output_files"]["self_contained_report"] = file_path
                        with open(result_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                        break
                
                # 检查report_files.json
                report_info_path = os.path.join(final_dir, "report_files.json")
                if os.path.exists(report_info_path) and (not file_path or not os.path.exists(file_path)):
                    try:
                        with open(report_info_path, "r", encoding="utf-8") as f:
                            report_info = json.load(f)
                        if "self_contained_report" in report_info and os.path.exists(report_info["self_contained_report"]):
                            file_path = report_info["self_contained_report"]
                            # 更新result中的路径
                            result["output_files"]["self_contained_report"] = file_path
                            with open(result_path, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        print(f"读取report_files.json时出错: {str(e)}")
            
            if not file_path or not os.path.exists(file_path):
                return jsonify({'error': '自包含报告文件不存在，请检查生成过程是否完整'}), 404
            
            return send_file(file_path, as_attachment=True, download_name=f"{industry}行业调研报告_自包含版.md")
        elif file_type == 'pdf':
            pdf_path = result["output_files"].get("final_report_pdf")
            if not pdf_path or not os.path.exists(pdf_path):
                return jsonify({'error': 'PDF文件不存在'}), 404
            return send_file(pdf_path, as_attachment=True, download_name=f"{industry}行业调研报告.pdf")
        elif file_type == 'complete':
            zip_path = result["output_files"].get("complete_zip")
            if not zip_path or not os.path.exists(zip_path):
                return jsonify({'error': '完整压缩包不存在'}), 404
            return send_file(zip_path, as_attachment=True, download_name=f"{industry}行业调研报告_完整版.zip")
        else:
            return jsonify({'error': '不支持的文件类型'}), 400
    except Exception as e:
        return jsonify({'error': f'下载文件时出错: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)