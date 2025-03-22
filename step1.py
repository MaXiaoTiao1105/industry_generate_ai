import os
import time
import uuid
import requests
import json
import re

# 获取 API Key（请确保环境变量已设置）
API_KEY = os.environ.get("ZHIPU_API_KEY", "")
API_URL = "https://open.bigmodel.cn/api/paas/v4/tools"
HEADERS = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

def safe_filename(s):
    """将字符串转换为安全的文件名"""
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    return s

def load_outline_and_prompts():
    """
    加载由 step0.py 生成的大纲和提示词
    """
    outline_path = os.path.join("reports", "step0", "report_outline.json")
    prompts_path = os.path.join("reports", "step0", "section_prompts.json")
    
    outline = None
    prompts = None
    
    # 加载大纲
    if os.path.exists(outline_path):
        try:
            with open(outline_path, "r", encoding="utf-8") as f:
                outline = json.load(f)
            print("成功加载报告大纲")
        except Exception as e:
            print(f"加载大纲时出错: {str(e)}")
    
    # 加载提示词
    if os.path.exists(prompts_path):
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                prompts = json.load(f)
            print("成功加载章节提示词")
        except Exception as e:
            print(f"加载提示词时出错: {str(e)}")
    
    # 如果没有找到有效的大纲或提示词，使用默认值
    if not outline:
        outline = {
            "main_title": "行业调研报告",
            "sections": [
                {
                    "title": "行业概况",
                    "subsections": [
                        {"title": "行业定义与分类", "search_terms": ["行业定义", "分类标准", "细分领域"]},
                        {"title": "发展历程", "search_terms": ["发展历史", "行业发展阶段", "发展特点"]}
                    ]
                },
                {
                    "title": "市场分析",
                    "subsections": [
                        {"title": "市场规模", "search_terms": ["市场规模", "增长率", "市场潜力"]},
                        {"title": "竞争格局", "search_terms": ["市场格局", "竞争态势", "主要企业"]},
                        {"title": "发展趋势", "search_terms": ["市场趋势", "发展前景", "未来走势"]}
                    ]
                }
            ]
        }
        print("未找到大纲文件，使用默认大纲")
    
    if not prompts:
        prompts = {}  # 没有预定义的提示词，将在搜索过程中生成
        print("未找到提示词文件，将使用默认提示词")
    
    return outline, prompts

def make_search_request(keyword, search_terms, specific_focus=None, retry_count=3):
    """调用搜索 API 获取原始内容"""
    all_content = []
    # 构建查询字符串
    search_query = f"{keyword} {' '.join(search_terms)}"
    if specific_focus:
        search_query += f" {specific_focus}"
    print(f"正在搜索: {search_query}")
    
    messages = [{"role": "user", "content": search_query}]
    for attempt in range(retry_count):
        try:
            data = {
                "request_id": str(uuid.uuid4()),
                "tool": "web-search-pro",
                "stream": False,
                "messages": messages
            }
            response = requests.post(
                API_URL,
                headers=HEADERS,
                json=data,
                timeout=300
            )
            if response.status_code == 200:
                result = response.json()
                content_parts = []
                for choice in result.get("choices", []):
                    message = choice.get("message", {})
                    for tool_call in message.get("tool_calls", []):
                        if tool_call.get("type") == "search_result":
                            search_results = tool_call.get("search_result", [])
                            for res in search_results:
                                content = res.get("content", "")
                                if content and len(content) > 50:
                                    content_parts.append(content)
                if content_parts:
                    all_content.extend(content_parts)
                    print("搜索成功，获取内容条数：", len(content_parts))
                    break
                else:
                    print(f"尝试 {attempt+1}/{retry_count} 未获取到足够内容。")
            else:
                print(f"API调用失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"调用搜索 API 出错: {str(e)}")
        time.sleep(3)
    if all_content:
        return "\n\n".join(all_content)
    else:
        return "未能找到相关行业信息。"

def save_prompt_for_summarization(output_dir, filename, prompt_template, content, keyword):
    """保存用于后续总结分析的提示词"""
    try:
        prompt_dir = os.path.join(output_dir, "prompts")
        os.makedirs(prompt_dir, exist_ok=True)
        
        # 生成实际的提示词（替换模板中的变量）
        actual_prompt = prompt_template.replace("{keyword}", keyword).replace("{content}", "")
        
        prompt_filename = f"{os.path.splitext(filename)[0]}_prompt.txt"
        prompt_path = os.path.join(prompt_dir, prompt_filename)
        
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(actual_prompt)
        
        print(f"已保存总结提示词至: {prompt_path}")
        return True
    except Exception as e:
        print(f"保存提示词时出错: {str(e)}")
        return False

def main():
    print("====== 行业调研报告内容收集工具 ======")
    
    # 加载由 step0.py 生成的大纲和提示词
    outline, section_prompts = load_outline_and_prompts()
    
    keyword = input("请输入要生成调研报告的行业关键词（如: 成品油、医疗器械等）：").strip()
    
    # 保存查询结果的目录
    output_dir = os.path.join("reports", "step1")
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存一份使用的大纲到 step1 目录
    outline_path = os.path.join(output_dir, "used_outline.json")
    try:
        with open(outline_path, "w", encoding="utf-8") as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        print(f"已保存使用的大纲至: {outline_path}")
    except Exception as e:
        print(f"保存大纲时出错: {str(e)}")
    
    # 遍历大纲中的各个章节和子章节
    for sec_idx, section in enumerate(outline["sections"], start=1):
        sec_title = section["title"]
        
        for sub_idx, subsection in enumerate(section.get("subsections", []), start=1):
            sub_title = subsection["title"]
            
            # 生成章节标识符
            section_key = f"{sec_idx}_{sub_idx}_{sub_title}"
            
            # 获取搜索关键词（优先使用预定义的提示词）
            if section_key in section_prompts:
                search_terms = section_prompts[section_key]["search_terms"]
                summary_prompt = section_prompts[section_key]["summary_prompt"]
            else:
                # 如果没有预定义的提示词，使用子章节中的search_terms
                search_terms = subsection.get("search_terms", ["行业分析", "市场趋势", "发展现状"])
                # 使用默认的总结提示词模板
                summary_prompt = f"""请对以下关于{{keyword}}行业的"{sec_title} - {sub_title}"部分内容进行归纳总结，要求：
1. 语言专业流畅，逻辑清晰；
2. 保持行业专业性，确保术语使用准确；
3. 采用连贯的段落叙述方式，每段500-600字左右，每个自然段围绕一个核心观点展开，并确保段落间有清晰的逻辑关系和过渡；
4. 保留重要的数据、事实和案例作为论据，并在适当的地方使用表格展示关键数据；
5. 保留原有的引用标记[x]，确保学术严谨性；
6. 按时间顺序或逻辑关系组织内容，结构清晰；
7. 确保最终内容既有深度分析，又具实用价值；
8. 在最后部分添加一个总结段落，分析这一章节内容的整体情况和关键点；
9. 输出原有的文章来源

原始内容：
{{content}}"""
            
            print(f"\n【{sec_idx}.{sub_idx}】 正在生成：{sec_title} - {sub_title}")
            print(f"使用搜索关键词: {', '.join(search_terms)}")
            
            # 搜索内容
            content = make_search_request(keyword, search_terms)
            
            # 生成 Markdown 格式内容
            md_content = f"# {keyword} - {sec_title}\n\n## {sub_title}\n\n{content}\n"
            
            # 构造安全的文件名
            filename = f"{sec_idx}_{sub_idx}_{safe_filename(sub_title)}.md"
            filepath = os.path.join(output_dir, filename)
            
            # 保存内容
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"保存内容至：{filepath}")
            
            # 保存用于后续总结的提示词
            save_prompt_for_summarization(output_dir, filename, summary_prompt, content, keyword)
            
            # 每个子章节间暂停，避免触发速率限制
            time.sleep(5)
    
    print("\n====== 内容收集完成 ======")
    print(f"所有内容已保存至: {output_dir}")
    print("请运行 step2.py 继续进行内容归纳总结。")

if __name__ == "__main__":
    main()