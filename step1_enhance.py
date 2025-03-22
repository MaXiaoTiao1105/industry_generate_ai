import os
import time
import uuid
import requests
import json
import re
from urllib.parse import urlparse
from datetime import datetime

# 获取 API Key（请确保环境变量已设置）
API_KEY = os.environ.get("ZHIPU_API_KEY", "zhipu-api-key")
API_URL = "https://open.bigmodel.cn/api/paas/v4/tools"
HEADERS = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

# 权威信息源域名白名单（可根据需要扩展）
AUTHORITY_DOMAINS = [
    "gov.cn",         # 政府网站
    "stats.gov.cn",   # 国家统计局
    "cnii.com.cn",    # 中国产业信息网
    "iresearch.cn",   # 艾瑞咨询
    "199it.com",      # 199IT互联网数据中心
    "chyxx.com",      # 产业研究院
    "askci.com",      # 中商产业研究院
    "cei.gov.cn",     # 中国经济信息网
    "ocn.com.cn",     # 中国产业网
    "cir.cn",         # 中研网
    "ceic.com",       # CEIC数据库
    "wind.com.cn",    # Wind数据库
    "sohu.com",       # 搜狐财经
    "cninfo.com.cn",  # 巨潮资讯
    "eastmoney.com",  # 东方财富网
    "sina.com.cn",    # 新浪财经
    "mofcom.gov.cn",  # 商务部
    "ndrc.gov.cn",    # 发改委
    "miit.gov.cn",    # 工信部
    "customs.gov.cn", # 海关总署
    "cia.gov",        # 美国中央情报局世界概况
    "worldbank.org",  # 世界银行
    "imf.org",        # 国际货币基金组织
    "pwccn.com",      # 普华永道
    "deloitte.com",   # 德勤
    "ey.com",         # 安永
    "kpmg.com",       # 毕马威
    "mckinsey.com",   # 麦肯锡
    "bcg.com",        # 波士顿咨询
    "bain.com",       # 贝恩咨询
    "cnpc.com.cn",    # 中国石油
    "sinopec.com",    # 中国石化
    "cnooc.com.cn",   # 中国海油
    "csrc.gov.cn",    # 证监会
    "pbc.gov.cn",     # 央行
    "cbrc.gov.cn",    # 银保监会
    "sse.com.cn",     # 上交所
    "szse.cn",        # 深交所
    "acfic.org.cn",   # 中华全国工商业联合会
]

def is_authoritative_source(url):
    """判断是否为权威信息源"""
    try:
        domain = urlparse(url).netloc
        # 检查域名是否在白名单中
        for auth_domain in AUTHORITY_DOMAINS:
            if auth_domain in domain:
                return True
        # 检查URL路径是否包含报告、白皮书等关键词
        path = urlparse(url).path.lower()
        report_keywords = ["report", "whitepaper", "研究报告", "白皮书", "蓝皮书", "行业报告", "分析", "调研"]
        for keyword in report_keywords:
            if keyword in path:
                return True
        return False
    except:
        return False

def get_quality_score(source_info):
    """根据来源信息评估质量分数"""
    score = 0
    
    # 检查是否有明确的出版日期，且不是太旧
    if "date" in source_info and source_info["date"]:
        try:
            pub_date = datetime.strptime(source_info["date"], "%Y-%m-%d")
            current_date = datetime.now()
            years_old = current_date.year - pub_date.year
            if years_old <= 1:
                score += 3  # 1年内发布的内容
            elif years_old <= 3:
                score += 2  # 3年内发布的内容
            else:
                score += 1  # 3年以上的旧内容
        except:
            pass
    
    # 检查是否有作者或发行机构
    if "author" in source_info and source_info["author"]:
        score += 1
    
    # 检查标题是否包含"报告"、"研究"等关键词
    if "title" in source_info and source_info["title"]:
        report_keywords = ["报告", "研究", "分析", "白皮书", "蓝皮书", "调研", "survey", "report", "research"]
        for keyword in report_keywords:
            if keyword in source_info["title"].lower():
                score += 1
                break
    
    # 检查来源网站是否权威
    if "url" in source_info and source_info["url"] and is_authoritative_source(source_info["url"]):
        score += 3
    
    return score

def safe_filename(s):
    """将字符串转换为安全的文件名"""
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    return s

def load_outline_and_prompts():
    """
    加载由 step0.py 生成的大纲和提示词
    """
    # 从环境变量中获取step0目录路径，如果没有则使用默认路径
    step0_dir = os.environ.get("REPORT_STEP0_DIR", os.path.join("reports", "step0"))
    
    outline_path = os.path.join(step0_dir, "report_outline.json")
    prompts_path = os.path.join(step0_dir, "section_prompts.json")
    
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
    """调用搜索 API 获取原始内容，同时收集引用信息"""
    all_content = []
    all_references = []
    
    # 构建查询字符串
    search_query = f"{keyword} {' '.join(search_terms)}"
    if specific_focus:
        search_query += f" {specific_focus}"
    print(f"正在搜索: {search_query}")
    
    # 每次调用时获取最新的API密钥
    current_api_key = os.environ.get("ZHIPU_API_KEY", API_KEY)
    headers = {
        "Authorization": current_api_key,
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "user", "content": f"{search_query} filetype:pdf OR filetype:doc OR 行业报告 OR 白皮书 OR 研究报告 OR 行业分析"}]
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
                headers=headers,
                json=data,
                timeout=300
            )
            if response.status_code == 200:
                result = response.json()
                content_parts = []
                ref_counter = 1
                references = []
                
                for choice in result.get("choices", []):
                    message = choice.get("message", {})
                    for tool_call in message.get("tool_calls", []):
                        if tool_call.get("type") == "search_result":
                            search_results = tool_call.get("search_result", [])
                            for res in search_results:
                                content = res.get("content", "")
                                
                                # 只有内容长度超过50且有效的才考虑
                                if content and len(content) > 50:
                                    # 收集引用信息
                                    source_info = {
                                        "title": res.get("title", "未知标题"),
                                        "url": res.get("url", ""),
                                        "date": res.get("date", ""),  # 可能需要从内容中提取或API中获取
                                        "author": res.get("author", "")  # 可能需要从内容中提取或API中获取
                                    }
                                    
                                    # 评估来源质量
                                    quality_score = get_quality_score(source_info)
                                    
                                    # 只接受较高质量的内容（分数≥3）
                                    if quality_score >= 3:
                                        # 为引用添加标记
                                        ref_id = ref_counter
                                        marked_content = f"{content} [ref{ref_id}]"
                                        
                                        # 添加到内容和引用列表
                                        content_parts.append(marked_content)
                                        
                                        references.append({
                                            "id": ref_id,
                                            "title": source_info["title"],
                                            "url": source_info["url"],
                                            "date": source_info["date"],
                                            "author": source_info["author"],
                                            "score": quality_score
                                        })
                                        
                                        ref_counter += 1
                
                if content_parts:
                    all_content.extend(content_parts)
                    all_references.extend(references)
                    print(f"搜索成功，获取内容条数：{len(content_parts)}，有效引用数：{len(references)}")
                    break
                else:
                    print(f"尝试 {attempt+1}/{retry_count} 未获取到足够内容。")
            else:
                print(f"API调用失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"调用搜索 API 出错: {str(e)}")
        time.sleep(3)

    # 如果没有找到有效内容，再尝试一次没有权威源筛选的搜索
    if not all_content:
        print("未找到足够权威的来源，尝试放宽搜索条件...")
        
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
                    headers=headers,
                    json=data,
                    timeout=300
                )
                if response.status_code == 200:
                    result = response.json()
                    content_parts = []
                    ref_counter = 1
                    references = []
                    
                    for choice in result.get("choices", []):
                        message = choice.get("message", {})
                        for tool_call in message.get("tool_calls", []):
                            if tool_call.get("type") == "search_result":
                                search_results = tool_call.get("search_result", [])
                                for res in search_results:
                                    content = res.get("content", "")
                                    if content and len(content) > 50:
                                        # 收集引用信息
                                        source_info = {
                                            "title": res.get("title", "未知标题"),
                                            "url": res.get("url", ""),
                                            "date": res.get("date", ""),
                                            "author": res.get("author", "")
                                        }
                                        
                                        # 为引用添加标记
                                        ref_id = ref_counter
                                        marked_content = f"{content} [ref{ref_id}]"
                                        
                                        # 添加到内容和引用列表
                                        content_parts.append(marked_content)
                                        
                                        references.append({
                                            "id": ref_id,
                                            "title": source_info["title"],
                                            "url": source_info["url"],
                                            "date": source_info["date"],
                                            "author": source_info["author"],
                                            "score": get_quality_score(source_info)
                                        })
                                        
                                        ref_counter += 1
                    
                    if content_parts:
                        all_content.extend(content_parts)
                        all_references.extend(references)
                        all_content.extend(content_parts)
                        all_references.extend(references)
                        print(f"搜索成功（放宽条件后），获取内容条数：{len(content_parts)}，引用数：{len(references)}")
                        break
                    else:
                        print(f"放宽条件后，尝试 {attempt+1}/{retry_count} 仍未获取到足够内容。")
                else:
                    print(f"API调用失败，状态码: {response.status_code}")
            except Exception as e:
                print(f"调用搜索 API 出错: {str(e)}")
            time.sleep(3)
    
    if all_content:
        content_text = "\n\n".join(all_content)
        return content_text, all_references
    else:
        return "未能找到相关行业信息。", []

def format_references_markdown(references):
    """将引用信息格式化为Markdown格式"""
    if not references:
        return ""
    
    md = "\n\n## 参考资料\n\n"
    for ref in references:
        ref_date = f", {ref['date']}" if ref.get("date") else ""
        ref_author = f", {ref['author']}" if ref.get("author") else ""
        ref_url = f", [{ref['url']}]({ref['url']})" if ref.get("url") else ""
        
        md += f"[ref{ref['id']}] {ref['title']}{ref_author}{ref_date}{ref_url}\n\n"
    
    return md

def save_prompt_for_summarization(output_dir, filename, prompt_template, content, keyword, references):
    """保存用于后续总结分析的提示词"""
    try:
        prompt_dir = os.path.join(output_dir, "prompts")
        os.makedirs(prompt_dir, exist_ok=True)
        
        # 添加引用信息到提示模板中
        refs_section = format_references_markdown(references).replace("\n\n", "\n")
        
        # 生成实际的提示词（替换模板中的变量）
        actual_prompt = prompt_template.replace("{keyword}", keyword).replace("{content}", "")
        
        # 添加引用处理指示
        additional_instructions = """
9. 在内容中保留原始引用标记，以确保信息来源可追溯；
10. 特别注意引用高质量、权威的信息源（如政府报告、行业权威机构报告）；
11. 如果不同信息源之间有冲突数据，注明不同来源的差异并分析可能的原因；
12. 确保所有重要数据、重要观点和行业趋势都有引用标记；
13.可以在每一个章节的最后部分，将来源列出，例如[1]是什么来源的， [2]是什么来源的

引用信息：
""" + refs_section
        
        # 将附加指示添加到提示词中
        if "要求：" in actual_prompt:
            actual_prompt = actual_prompt.replace("要求：", f"要求：\n{additional_instructions}\n")
        else:
            actual_prompt += "\n" + additional_instructions
        
        prompt_filename = f"{os.path.splitext(filename)[0]}_prompt.txt"
        prompt_path = os.path.join(prompt_dir, prompt_filename)
        
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(actual_prompt)
        
        print(f"已保存总结提示词至: {prompt_path}")
        return True
    except Exception as e:
        print(f"保存提示词时出错: {str(e)}")
        return False

def save_references_json(output_dir, filename, references):
    """保存引用信息为JSON格式"""
    try:
        refs_dir = os.path.join(output_dir, "references")
        os.makedirs(refs_dir, exist_ok=True)
        
        refs_filename = f"{os.path.splitext(filename)[0]}_references.json"
        refs_path = os.path.join(refs_dir, refs_filename)
        
        with open(refs_path, "w", encoding="utf-8") as f:
            json.dump(references, f, ensure_ascii=False, indent=2)
        
        print(f"已保存引用信息至: {refs_path}")
        return True
    except Exception as e:
        print(f"保存引用信息时出错: {str(e)}")
        return False

def main():
    print("====== 行业调研报告内容收集工具 (带引用追踪) ======")
    
    # 加载由 step0.py 生成的大纲和提示词
    outline, section_prompts = load_outline_and_prompts()
    
    keyword = input("请输入要生成调研报告的行业关键词（如: 成品油、医疗器械等）：").strip()
    
    # 从环境变量中获取step1目录路径，如果没有则使用默认路径
    step1_dir = os.environ.get("REPORT_STEP1_DIR", os.path.join("reports", "step1"))
    
    # 保存查询结果的目录
    output_dir = step1_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存一份使用的大纲到 step1 目录
    outline_path = os.path.join(output_dir, "used_outline.json")
    try:
        with open(outline_path, "w", encoding="utf-8") as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        print(f"已保存使用的大纲至: {outline_path}")
    except Exception as e:
        print(f"保存大纲时出错: {str(e)}")
    
    # 创建一个引用汇总列表，用于最终生成一份完整的参考文献
    all_references = []
    
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
5. 保留原有的引用标记[refX]，确保学术严谨性；
6. 按时间顺序或逻辑关系组织内容，结构清晰；
7. 确保最终内容既有深度分析，又具实用价值；
8. 在最后部分添加一个总结段落，分析这一章节内容的整体情况和关键点；

原始内容：
{{content}}"""
            
            print(f"\n【{sec_idx}.{sub_idx}】 正在生成：{sec_title} - {sub_title}")
            print(f"使用搜索关键词: {', '.join(search_terms)}")
            
            # 搜索内容（现在返回内容和引用信息）
            content, references = make_search_request(keyword, search_terms)
            
            # 添加到全局引用列表
            for ref in references:
                if not any(existing_ref['url'] == ref['url'] for existing_ref in all_references if 'url' in existing_ref and ref.get('url')):
                    # 更新引用ID以保持全局一致性
                    ref['global_id'] = len(all_references) + 1
                    all_references.append(ref)
            
            # 生成引用部分的Markdown
            refs_md = format_references_markdown(references)
            
            # 生成 Markdown 格式内容
            md_content = f"# {keyword} - {sec_title}\n\n## {sub_title}\n\n{content}\n\n{refs_md}"
            
            # 构造安全的文件名
            filename = f"{sec_idx}_{sub_idx}_{safe_filename(sub_title)}.md"
            filepath = os.path.join(output_dir, filename)
            
            # 保存内容
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"保存内容至：{filepath}")
            
            # 保存用于后续总结的提示词
            save_prompt_for_summarization(output_dir, filename, summary_prompt, content, keyword, references)
            
            # 保存引用信息的JSON文件
            save_references_json(output_dir, filename, references)
            
            # 每个子章节间暂停，避免触发速率限制
            time.sleep(5)
    
    # 保存完整的参考文献列表
    refs_filepath = os.path.join(output_dir, "all_references.json")
    with open(refs_filepath, "w", encoding="utf-8") as f:
        json.dump(all_references, f, ensure_ascii=False, indent=2)
    print(f"已保存完整参考文献列表至: {refs_filepath}")
    
    # 生成参考文献的Markdown格式
    all_refs_md = f"# {keyword}行业报告 - 参考文献\n\n"
    refs_by_quality = sorted(all_references, key=lambda x: x.get('score', 0), reverse=True)
    for ref in refs_by_quality:
        ref_date = f", {ref['date']}" if ref.get("date") else ""
        ref_author = f", {ref['author']}" if ref.get("author") else ""
        ref_url = f", [{ref['url']}]({ref['url']})" if ref.get("url") else ""
        ref_score = f" (质量评分: {ref.get('score', 'N/A')})"
        
        all_refs_md += f"[{ref.get('global_id', ref.get('id', 'N/A'))}] {ref['title']}{ref_author}{ref_date}{ref_url}{ref_score}\n\n"
    
    refs_md_path = os.path.join(output_dir, "references.md")
    with open(refs_md_path, "w", encoding="utf-8") as f:
        f.write(all_refs_md)
    print(f"已生成完整参考文献Markdown至: {refs_md_path}")
    
    print("\n====== 内容收集完成 ======")
    print(f"所有内容已保存至: {output_dir}")
    print("请运行 step2.py 继续进行内容归纳总结。")

if __name__ == "__main__":
    main()