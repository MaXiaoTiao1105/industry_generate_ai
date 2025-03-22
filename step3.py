import os
import json
import re
import shutil
import base64
from datetime import datetime

def extract_section_numbers(filename):
    """从文件名提取章节号，用于排序"""
    parts = os.path.splitext(filename)[0].split('_')
    try:
        # 假设文件名格式是 1_1_章节名_反思优化.md
        section = int(parts[0])
        subsection = int(parts[1])
        return (section, subsection)
    except (ValueError, IndexError):
        return (999, 999)  # 如果无法解析，放到最后

def extract_section_title(content):
    """从文件内容提取章节标题"""
    # 尝试提取二级标题（##）
    match = re.search(r'^##\s*(.+)', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # 如果没有二级标题，尝试提取一级标题（#）
    match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    return "未命名章节"

def generate_toc(sections):
    """生成目录"""
    toc = ["## 目录\n"]
    
    current_section = None
    
    for sec in sections:
        section_num, subsection_num = sec['numbers']
        
        # 如果是新的一级章节
        if current_section != section_num:
            current_section = section_num
            toc.append(f"{section_num}. {sec['section_title']}")
        
        # 添加子章节
        toc.append(f"  {section_num}.{subsection_num}. {sec['subsection_title']}")
    
    return "\n".join(toc)

def copy_images(input_dir, output_dir):
    """复制charts文件夹到输出目录"""
    # 使用正确的相对路径
    charts_dir = os.path.join(input_dir, "charts")
    if os.path.exists(charts_dir):
        output_charts_dir = os.path.join(output_dir, "charts")
        # 如果output_charts_dir已存在，先删除它
        if os.path.exists(output_charts_dir):
            shutil.rmtree(output_charts_dir)
        # 复制整个charts文件夹到输出目录
        shutil.copytree(charts_dir, output_charts_dir)
        print(f"已复制图表文件夹到: {output_charts_dir}")
    else:
        print(f"未找到charts文件夹: {charts_dir}，图片可能无法正确显示")
    return os.path.exists(charts_dir), charts_dir

def create_self_contained_markdown(content, charts_dir):
    """将Markdown中的外部图片转换为内联的base64格式"""
    def replace_image(match):
        img_path = match.group(2)
        # 处理相对路径
        if not os.path.isabs(img_path):
            # 如果路径以"charts/"开头，则直接使用
            if img_path.startswith('charts/'):
                full_path = os.path.join(os.path.dirname(charts_dir), img_path)
            else:
                # 否则，假设路径相对于charts目录
                full_path = os.path.join(charts_dir, img_path)
        else:
            full_path = img_path
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            print(f"警告: 图片文件不存在: {full_path}")
            return match.group(0)  # 保持原样
        
        # 获取MIME类型
        file_ext = os.path.splitext(full_path)[1].lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }.get(file_ext, 'application/octet-stream')
        
        # 读取文件并转换为base64
        with open(full_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        # 返回内联图片
        return f'{match.group(1)}data:{mime_type};base64,{img_data}{match.group(3)}'
    
    # 匹配Markdown中的图片引用: ![alt](path "title")
    image_pattern = r'(!\[.*?\]\()([^"\)]+)(\s*(?:".*?")?\))'
    return re.sub(image_pattern, replace_image, content)

def ensure_relative_paths(content):
    """确保图片路径都是相对路径"""
    def replace_image_path(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        title = match.group(3) or ''
        
        # 转换绝对路径为相对路径
        if os.path.isabs(img_path):
            base_name = os.path.basename(img_path)
            relative_path = os.path.join('charts', base_name)
            return f'![{alt_text}]({relative_path}{title})'
        elif not img_path.startswith('charts/') and not img_path.startswith('./charts/'):
            # 如果不是以charts/开头，添加前缀
            relative_path = os.path.join('charts', img_path)
            return f'![{alt_text}]({relative_path}{title})'
        
        # 已经是相对路径，保持原样
        return match.group(0)
    
    # 匹配Markdown中的图片引用: ![alt](path "title")
    # 使用更精确的正则表达式匹配图片标签
    image_pattern = r'!\[(.*?)\]\(([^"\)]+)(\s*"[^"]*")?\)'
    return re.sub(image_pattern, replace_image_path, content)

def merge_report():
    """合并生成最终报告"""
    # 从环境变量中获取目录路径，如果没有则使用默认路径
    step0_dir = os.environ.get("REPORT_STEP0_DIR", os.path.join("reports", "step0"))
    step2_dir = os.environ.get("REPORT_STEP2_DIR", os.path.join("reports", "step2"))
    final_dir = os.environ.get("REPORT_FINAL_DIR", os.path.join("reports", "final"))
    
    input_dir = step2_dir
    output_dir = final_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # 复制图片文件夹
    charts_exist, charts_dir = copy_images(input_dir, output_dir)
    
    # 加载大纲获取章节标题
    outline_path = os.path.join(step0_dir, "report_outline.json")
    outline = {}
    try:
        if os.path.exists(outline_path):
            with open(outline_path, "r", encoding="utf-8") as f:
                outline = json.load(f)
    except Exception as e:
        print(f"加载大纲时出错: {str(e)}")
    
    keyword = input("请输入报告的行业关键词（与前两步保持一致）：").strip()
    current_date = datetime.now().strftime("%Y年%m月%d日")
    
    # 获取所有优化后的文件
    file_list = [f for f in os.listdir(input_dir) if f.endswith("_optimized.md")]
    
    # 按章节顺序排序
    file_list.sort(key=extract_section_numbers)
    
    # 提取章节信息
    sections = []
    for filename in file_list:
        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 从文件名提取章节号
        section_numbers = extract_section_numbers(filename)
        
        # 从大纲中查找章节标题
        section_title = ""
        subsection_title = ""
        
        # 尝试从大纲中找到对应章节标题
        if outline and "sections" in outline:
            try:
                section_idx = section_numbers[0] - 1
                subsection_idx = section_numbers[1] - 1
                
                if section_idx < len(outline["sections"]):
                    section_title = outline["sections"][section_idx]["title"]
                    subsections = outline["sections"][section_idx].get("subsections", [])
                    if subsection_idx < len(subsections):
                        subsection_title = subsections[subsection_idx]["title"]
            except (IndexError, KeyError):
                pass
        
        # 如果从大纲中找不到，从文件名和内容中提取
        if not section_title:
            parts = os.path.splitext(filename)[0].split('_')
            if len(parts) >= 3:
                section_title = parts[2]
        
        if not subsection_title:
            subsection_title = extract_section_title(content)
        
        # 确保内容中的图片引用都是相对路径
        content = ensure_relative_paths(content)
        
        sections.append({
            'filename': filename,
            'content': content,
            'numbers': section_numbers,
            'section_title': section_title,
            'subsection_title': subsection_title
        })
    
    # 生成报告
    report_lines = []
    
    # 添加标题和元数据
    report_title = f"{keyword}行业调研报告"
    if outline and "main_title" in outline and outline["main_title"]:
        report_title = outline["main_title"].replace("{industry}", keyword)
    
    report_lines.append(f"# {report_title}")
    report_lines.append(f"*生成日期：{current_date}*\n")
    report_lines.append("---\n")
    
    # 添加目录
    report_lines.append(generate_toc(sections))
    report_lines.append("\n---\n")
    
    # 组织章节内容
    current_section = None
    
    for sec in sections:
        section_num, subsection_num = sec['numbers']
        
        # 如果是新的章节，添加章节标题
        if current_section != section_num:
            current_section = section_num
            report_lines.append(f"\n## {section_num}. {sec['section_title']}\n")
        
        # 添加子章节标题和内容
        report_lines.append(f"### {section_num}.{subsection_num}. {sec['subsection_title']}\n")
        
        # 移除内容中已有的标题（避免重复）
        content = sec['content']
        content = re.sub(r'^#\s*.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^##\s*.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^###\s*.*$', '', content, flags=re.MULTILINE)
        
        report_lines.append(content.strip())
        report_lines.append("\n")
    
    # 合并为最终报告
    final_report = "\n".join(report_lines)
    
    # 保存标准Markdown报告（使用相对路径的图片引用）
    output_file = os.path.join(output_dir, f"{keyword}行业调研报告_最终版.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_report)
    
    # 结果信息字典
    result_info = {
        "final_report": output_file
    }
    
    # 创建自包含的Markdown文件（内联图片的base64格式）
    if charts_exist:
        self_contained_report = create_self_contained_markdown(final_report, os.path.join(output_dir, "charts"))
        self_contained_file = os.path.join(output_dir, f"{keyword}行业调研报告_自包含版.md")
        with open(self_contained_file, "w", encoding="utf-8") as f:
            f.write(self_contained_report)
        result_info["self_contained_report"] = self_contained_file
        print(f"\n自包含Markdown报告（内联图片）生成完成，保存为：{self_contained_file}")
    
    # 将结果信息写入到特定文件
    report_info_path = os.path.join(output_dir, "report_files.json")
    with open(report_info_path, "w", encoding="utf-8") as f:
        json.dump(result_info, f, ensure_ascii=False, indent=2)
    
    print(f"\n标准报告生成完成，保存为：{output_file}")
    print(f"图片路径为：{os.path.join(output_dir, 'charts')}目录下的图片文件")
    print(f"报告文件信息已保存至：{report_info_path}")

if __name__ == "__main__":
    merge_report()