import os
import time
import json
import re
import uuid
import requests
from openai import OpenAI
from math import log  # Moved this import to the top

# 获取API Key（请确保环境变量已设置）
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "zhipu-api-key")
DS_API_KEY = os.environ.get("DS_API_KEY", "deepseek-api-key")

# 初始化API客户端
zhipu_headers = {
    "Authorization": ZHIPU_API_KEY,
    "Content-Type": "application/json"
}
zhipu_api_url = "https://open.bigmodel.cn/api/paas/v4/tools"

# 初始化deepseek客户端
ds_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com")

class ThinkCiteProcessor:
    """
    实现Think&Cite框架的处理器，使用自引导蒙特卡洛树搜索（SG-MCTS）增强内容生成
    """
    def __init__(self):
        self.zhipu_api_url = zhipu_api_url
        self.zhipu_headers = zhipu_headers
        self.ds_client = ds_client
        self.mcts_depth = 3
        self.mcts_iterations = 5
        self.ucb_c = 1.41  # UCB算法的探索参数

    def search_references(self, query, keyword, retry_count=3):
        """
        搜索相关参考资料作为引用来源
        """
        all_content = []
        search_query = f"{keyword} {query}"
        print(f"正在搜索引用资料: {search_query}")
        
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
                    self.zhipu_api_url,
                    headers=self.zhipu_headers,
                    json=data,
                    timeout=300
                )
                
                if response.status_code == 200:
                    result = response.json()
                    references = []
                    urls = []
                    
                    for choice in result.get("choices", []):
                        message = choice.get("message", {})
                        for tool_call in message.get("tool_calls", []):
                            if tool_call.get("type") == "search_result":
                                search_results = tool_call.get("search_result", [])
                                for res in search_results:
                                    content = res.get("content", "")
                                    title = res.get("title", "未知标题")
                                    url = res.get("url", "")
                                    
                                    if content and len(content) > 50 and url not in urls:
                                        references.append({
                                            "title": title,
                                            "url": url,
                                            "content": content,
                                            "snippet": content[:300] + "..." if len(content) > 300 else content
                                        })
                                        urls.append(url)
                    
                    if references:
                        return references
                    else:
                        print(f"尝试 {attempt+1}/{retry_count} 未获取到足够引用内容。")
                else:
                    print(f"引用搜索API调用失败，状态码: {response.status_code}")
            except Exception as e:
                print(f"调用引用搜索API出错: {str(e)}")
            time.sleep(3)
        
        return []

    def evaluate_citation_quality(self, text, citations):
        """
        评估引用质量，包括引用召回率和精确率
        """
        prompt = f"""
请评估以下文本中引用的质量。文本内容如下：

{text}

引用的资料如下：

{json.dumps(citations, ensure_ascii=False, indent=2)}

请从以下几个方面对引用质量评分（0-10分）：
1. 引用精确率：引用的资料是否准确支持文本中的论点？
2. 引用召回率：文本中的关键论点是否都有相应引用支持？
3. 引用相关性：引用的内容与文章主题的相关度如何？
4. 引用新鲜度：引用的信息是否足够新近和时效性强？

请给出分数并解释原因。
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in evaluating citation quality."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            for retry in range(3):  # 添加重试机制
                try:
                    response = self.ds_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.2,
                        stream=False
                    )
                    
                    evaluation = response.choices[0].message.content
                    # 提取评分
                    scores = re.findall(r'(\d+)[./]10', evaluation)
                    if scores:
                        # 计算平均分
                        avg_score = sum(map(int, scores)) / len(scores)
                        normalized_score = avg_score / 10.0  # 归一化到0-1
                        return normalized_score, evaluation
                    else:
                        return 0.5, evaluation  # 默认中等分数
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 (尝试 {retry+1}/3): {str(e)}")
                    time.sleep(5)  # 等待5秒后重试
                except Exception as e:
                    print(f"API调用错误 (尝试 {retry+1}/3): {str(e)}")
                    time.sleep(5)  # 等待5秒后重试
            
            # 所有重试都失败，返回默认值
            print("所有重试都失败，使用默认评分")
            return 0.4, "评估引用质量失败，API调用出错。"
        except Exception as e:
            print(f"评估引用质量时出错: {str(e)}")
            return 0.4, "评估引用质量失败。"

    def evaluate_content_quality(self, text):
        """
        评估内容质量
        """
        prompt = f"""
请评估以下行业报告内容的质量。内容如下：

{text[:3000] + "..." if len(text) > 3000 else text}

请从以下几个方面对内容质量评分（0-10分）：
1. 内容专业性：内容是否体现行业专业知识和深度？
2. 内容结构：内容是否有清晰的结构和逻辑？
3. 表达准确性：文字表达是否准确、清晰？
4. 信息价值：内容是否为读者提供有价值的信息？

请给出分数并解释原因。
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in evaluating content quality."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            for retry in range(3):  # 添加重试机制
                try:
                    response = self.ds_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.2,
                        stream=False
                    )
                    
                    evaluation = response.choices[0].message.content
                    # 提取评分
                    scores = re.findall(r'(\d+)[./]10', evaluation)
                    if scores:
                        # 计算平均分
                        avg_score = sum(map(int, scores)) / len(scores)
                        normalized_score = avg_score / 10.0  # 归一化到0-1
                        return normalized_score, evaluation
                    else:
                        return 0.5, evaluation  # 默认中等分数
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 (尝试 {retry+1}/3): {str(e)}")
                    time.sleep(5)  # 等待5秒后重试
                except Exception as e:
                    print(f"API调用错误 (尝试 {retry+1}/3): {str(e)}")
                    time.sleep(5)  # 等待5秒后重试
            
            # 所有重试都失败，返回默认值
            print("所有重试都失败，使用默认评分")
            return 0.4, "评估内容质量失败，API调用出错。"
        except Exception as e:
            print(f"评估内容质量时出错: {str(e)}")
            return 0.4, "评估内容质量失败。"

    def generate_with_citations(self, content, section_title, keyword):
        """
        使用Think&Cite框架生成带引用的内容
        """
        # 使用MCTS搜索最佳生成路径
        root_node = {
            "text": "",
            "citations": [],
            "children": [],
            "visits": 0,
            "reward": 0,
            "depth": 0,
            "parent": None,
            "memory": []  # Reflexion框架的记忆
        }
        
        best_node = self.mcts_search(root_node, content, section_title, keyword)
        
        # 构建最终带引用的文本
        final_text = best_node["text"]
        citations = best_node["citations"]
        
        # 添加引用列表
        if citations:
            final_text += "\n\n## 参考资料\n"
            for i, citation in enumerate(citations):
                final_text += f"{i+1}. [{citation['title']}]({citation['url']})\n"
        
        return final_text

    def mcts_search(self, root_node, original_content, section_title, keyword):
        """
        执行MCTS搜索，找到最佳生成路径
        """
        print(f"开始MCTS搜索，共{self.mcts_iterations}轮迭代...")
        
        for iteration in range(self.mcts_iterations):
            print(f"第{iteration+1}轮MCTS迭代...")
            
            # 选择
            selected_node = self.selection(root_node)
            
            # 扩展
            if selected_node["depth"] < self.mcts_depth and (not selected_node["children"]):
                expanded_nodes = self.expansion(selected_node, original_content, section_title, keyword)
                
                # 评估每个新节点
                for node in expanded_nodes:
                    reward = self.evaluation(node)
                    self.backpropagation(node, reward)
            else:
                # 如果已达最大深度或无法扩展，直接评估当前节点
                reward = self.evaluation(selected_node)
                self.backpropagation(selected_node, reward)
        
        # 返回访问次数最多的子节点作为最终结果
        if not root_node["children"]:
            return root_node
        
        best_child = max(root_node["children"], key=lambda child: child["visits"])
        return best_child

    def selection(self, node):
        """
        使用UCT算法选择最优节点
        """
        current_node = node
        
        # 如果当前节点是叶节点或未完全展开，返回该节点
        if not current_node["children"] or current_node["depth"] >= self.mcts_depth:
            return current_node
        
        # 使用UCB公式选择最优子节点
        best_score = -float('inf')
        best_child = None
        
        for child in current_node["children"]:
            # 避免除零错误
            if child["visits"] == 0:
                return child
            
            # UCB得分 = 平均奖励 + C * sqrt(ln(父节点访问次数) / 子节点访问次数)
            exploit = child["reward"] / child["visits"]
            explore = self.ucb_c * (2 * (log(current_node["visits"]) / child["visits"]) ** 0.5)
            ucb_score = exploit + explore
            
            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child
        
        if best_child is None:
            return current_node
        
        # 递归选择
        return self.selection(best_child)

    def expansion(self, node, original_content, section_title, keyword):
        """
        扩展节点，实现Think-Verbalize-Cite过程
        """
        # 已有的文本
        current_text = node["text"]
        
        # 根据已有内容和原始内容，生成新的思考方向
        think_prompt = f"""
我正在为"{keyword}行业 - {section_title}"撰写内容。目前已有的内容是：

{current_text if current_text else "尚未开始撰写。"}

原始参考资料：

{original_content[:2000] + "..." if len(original_content) > 2000 else original_content}

请思考并提出3个不同的关键观点或论点，用于扩展当前内容。每个观点需要具体、明确，并且可以通过引用外部资料来支持。

要求：
1. 每个观点需要具体、明确，能展示行业专业性
2. 观点之间应有差异，覆盖不同角度
3. 每个观点后提供2-3个可能的搜索关键词，用于寻找支持该观点的引用资料

请按以下格式输出：

观点1：[具体观点]
搜索关键词：[关键词1],[关键词2],[关键词3]

观点2：[具体观点]
搜索关键词：[关键词1],[关键词2],[关键词3]

观点3：[具体观点] 
搜索关键词：[关键词1],[关键词2],[关键词3]
"""
        
        # 从记忆中获取反思内容
        memory_content = ""
        if node["memory"]:
            memory_content = "\n\n过去的反思记录：\n" + "\n".join(node["memory"])
            think_prompt += memory_content
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in industry research."},
                {"role": "user", "content": think_prompt}
            ]
            
            think_response = self.ds_client.chat.completions.create(
                model="deepseek-reasoner",
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                stream=False
            )
            
            think_result = think_response.choices[0].message.content
            
            # 解析思考结果，获取观点和搜索关键词
            viewpoints = []
            pattern = r"观点(\d+)：(.*?)\n搜索关键词：(.*?)(?=\n\n观点\d+：|\Z)"
            matches = re.findall(pattern, think_result, re.DOTALL)
            
            if not matches:
                # 尝试其他可能的格式
                pattern = r"(\d+)[\.、)]\s*(.*?)\n.*?关键词[：:](.*?)(?=\n\n\d+[\.、)]|\Z)"
                matches = re.findall(pattern, think_result, re.DOTALL)
            
            for match in matches:
                if len(match) >= 3:
                    viewpoint = match[1].strip()
                    keywords = [k.strip() for k in match[2].split(",")]
                    viewpoints.append({"viewpoint": viewpoint, "keywords": keywords})
            
            # 如果没有匹配到观点，尝试直接提取
            if not viewpoints:
                # 简单分割文本尝试提取
                sections = think_result.split("\n\n")
                for section in sections:
                    if "观点" in section or "：" in section:
                        lines = section.split("\n")
                        if len(lines) >= 2:
                            viewpoint = lines[0].split("：")[-1].strip()
                            keywords = []
                            for line in lines[1:]:
                                if "关键词" in line:
                                    keywords = [k.strip() for k in line.split("：")[-1].split(",")]
                                    break
                            if viewpoint and keywords:
                                viewpoints.append({"viewpoint": viewpoint, "keywords": keywords})
            
            # 确保有至少一个观点
            if not viewpoints:
                viewpoints = [{
                    "viewpoint": "行业发展现状与趋势", 
                    "keywords": [f"{keyword} 发展现状", f"{keyword} 行业趋势", f"{keyword} 市场规模"]
                }]
            
            # 限制最多3个观点以控制搜索次数
            viewpoints = viewpoints[:3]
            
            # 为每个观点搜索引用并生成内容
            expanded_nodes = []
            
            for vp_index, vp in enumerate(viewpoints):
                print(f"正在处理观点{vp_index+1}: {vp['viewpoint']}")
                
                # 搜索引用
                search_query = " ".join(vp["keywords"][:2])  # 使用前两个关键词
                citations = self.search_references(search_query, keyword)
                
                if not citations:
                    print(f"未找到观点{vp_index+1}的引用资料，尝试使用更广泛的关键词")
                    # 使用更通用的关键词再搜索一次
                    broader_query = f"{keyword} {vp['viewpoint']}"
                    citations = self.search_references(broader_query, keyword)
                
                # 使用思考结果和引用生成内容
                verbalize_prompt = f"""
我正在为"{keyword}行业 - {section_title}"撰写内容。当前需要详细阐述以下观点：

{vp['viewpoint']}

已经搜索到的相关引用资料：
"""
                for i, cite in enumerate(citations):
                    verbalize_prompt += f"""
引用[{i+1}] {cite['title']}:
{cite['snippet']}
"""
                
                verbalize_prompt += f"""
已有的文本内容：
{current_text}

请基于以上引用资料，撰写一段详细阐述该观点的内容（约300-500字）。要求：
1. 必须严格基于引用资料的事实撰写，不要添加未在引用中提及的具体数据
2. 在适当位置标注引用编号，如[1]、[2]等
3. 保持专业、客观的语言风格
4. 确保与已有内容在逻辑上连贯
5. 可以从引用资料中提取关键数据或观点，但要确保准确
"""
                # 加入反思记忆，改进生成
                if node["memory"]:
                    verbalize_prompt += f"\n\n请注意改进以下方面（基于过去的反思）：\n" + "\n".join(node["memory"])
                
                try:
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant specialized in industry research report writing."},
                        {"role": "user", "content": verbalize_prompt}
                    ]
                    
                    verbalize_response = self.ds_client.chat.completions.create(
                        model="deepseek-reasoner",
                        messages=messages,
                        max_tokens=2000,
                        temperature=0.7,
                        stream=False
                    )
                    
                    new_content = verbalize_response.choices[0].message.content
                    
                    # 构建新节点
                    new_text = current_text + ("\n\n" if current_text else "") + new_content
                    new_node = {
                        "text": new_text,
                        "citations": citations,
                        "children": [],
                        "visits": 1,
                        "reward": 0,
                        "depth": node["depth"] + 1,
                        "parent": node,
                        "memory": node["memory"].copy()  # 继承父节点的记忆
                    }
                    
                    # 添加到子节点列表
                    node["children"].append(new_node)
                    expanded_nodes.append(new_node)
                    
                except Exception as e:
                    print(f"生成内容时出错: {str(e)}")
            
            return expanded_nodes
            
        except Exception as e:
            print(f"思考过程出错: {str(e)}")
            return []

    def evaluation(self, node):
        """
        评估节点质量，实现过程奖励模型
        """
        if not node["text"]:
            return 0
        
        # 1. 评估生成内容质量
        content_score, content_eval = self.evaluate_content_quality(node["text"])
        
        # 2. 评估引用质量
        citation_score, citation_eval = self.evaluate_citation_quality(node["text"], node["citations"])
        
        # 综合得分，内容质量和引用质量各占50%
        total_score = 0.6 * content_score + 0.4 * citation_score
        
        # Reflexion: 生成反思并更新记忆
        self.reflexion(node, content_eval, citation_eval, total_score)
        
        return total_score

    def reflexion(self, node, content_eval, citation_eval, total_score):
        """
        实现Reflexion框架中的反思机制
        """
        reflexion_prompt = f"""
请基于以下评估，对内容进行深度反思和改进建议：

内容质量评估：
{content_eval}

引用质量评估：
{citation_eval}

总体评分：{total_score:.2f}/1.0

请针对以上评估，提出3-5条具体、可操作的改进建议，帮助后续内容生成提高质量。建议应当明确、具体，可以直接指导内容生成。
"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in critical analysis and reflection."},
                {"role": "user", "content": reflexion_prompt}
            ]
            
            reflexion_response = self.ds_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=1000,
                temperature=0.5,
                stream=False
            )
            
            reflexion_result = reflexion_response.choices[0].message.content
            
            # 提取关键建议（最多保留3条）
            suggestions = re.findall(r'\d+\.\s*(.*?)(?=\n\d+\.|\Z)', reflexion_result, re.DOTALL)
            key_suggestions = [s.strip() for s in suggestions[:3] if len(s.strip()) > 10]
            
            # 如果没有提取到建议，尝试其他方式
            if not key_suggestions:
                lines = reflexion_result.split('\n')
                for line in lines:
                    if line.strip() and len(line.strip()) > 20 and not line.startswith("总体") and not line.startswith("内容质量") and not line.startswith("引用质量"):
                        key_suggestions.append(line.strip())
                        if len(key_suggestions) >= 3:
                            break
            
            # 更新节点的记忆
            node["memory"].extend(key_suggestions)
            
            # 限制记忆大小，保留最近的5条
            if len(node["memory"]) > 5:
                node["memory"] = node["memory"][-5:]
            
            return key_suggestions
            
        except Exception as e:
            print(f"生成反思时出错: {str(e)}")
            return []

    def backpropagation(self, node, reward):
        """
        反向传播奖励值
        """
        current = node
        while current:
            current["visits"] += 1
            current["reward"] += reward
            current = current["parent"]


def process_content_with_thinkcite(section_file, keyword):
    """
    处理单个章节文件，使用Think&Cite框架进行内容增强
    """
    print(f"\n正在使用Think&Cite框架处理文件: {section_file}")
    
    # 加载原始内容
    input_dir = os.path.join("reports", "step1")
    input_path = os.path.join(input_dir, section_file)
    
    with open(input_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    
    # 提取章节标题
    section_title = ""
    headers = re.findall(r"^##\s+(.+)$", original_content, re.MULTILINE)
    if headers:
        section_title = headers[0].strip()
    else:
        # 尝试从文件名提取
        parts = os.path.splitext(section_file)[0].split("_")
        if len(parts) >= 3:
            section_title = "_".join(parts[2:])
    
    # 初始化处理器
    processor = ThinkCiteProcessor()
    
    # 使用Think&Cite框架增强内容
    enhanced_content = processor.generate_with_citations(original_content, section_title, keyword)
    
    # 保存增强后的内容
    output_dir = os.path.join("reports", "step1_5")
    os.makedirs(output_dir, exist_ok=True)
    
    output_filename = f"{os.path.splitext(section_file)[0]}_enhanced.md"
    output_path = os.path.join(output_dir, output_filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(enhanced_content)
    
    print(f"已保存增强内容至: {output_path}")
    return output_path

def main():
    print("====== Think&Cite 框架内容增强工具 ======")
    
    # 获取行业关键词
    keyword = input("请输入行业关键词（与 step1 保持一致）：").strip()
    
    # 创建输出目录
    output_dir = os.path.join("reports", "step1_5")
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取 step1 中生成的所有 Markdown 文件
    input_dir = os.path.join("reports", "step1")
    md_files = [f for f in os.listdir(input_dir) if f.endswith(".md")]
    
    print(f"找到 {len(md_files)} 个章节文件需要处理")
    
    # 处理每个文件
    processed_files = []
    for i, md_file in enumerate(md_files):
        print(f"\n[{i+1}/{len(md_files)}] 处理文件: {md_file}")
        output_file = process_content_with_thinkcite(md_file, keyword)
        processed_files.append(output_file)
        time.sleep(5)  # 避免API请求过于频繁
    
    # 生成处理报告
    report = {
        "keyword": keyword,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processed_files": processed_files,
        "total_files": len(md_files)
    }
    
    report_path = os.path.join(output_dir, "processing_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("\n====== Think&Cite 内容增强完成 ======")
    print(f"所有增强内容已保存至: {output_dir}")
    print("请运行 step2.py 继续进行内容归纳总结。")

if __name__ == "__main__":
    main()