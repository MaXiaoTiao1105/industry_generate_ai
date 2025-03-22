import os
import time
import json
import re
from openai import OpenAI

# 请确保环境变量 API_KEY 已设置，否则请直接在下面替换为你的 API Key
API_KEY = os.environ.get("DS_API_KEY", "deepseek-api-key")

# 初始化 deepseek 客户端
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

class TemplateGeneralizer:
    """
    分析特定行业的报告模板，提取通用结构，并生成适用于不同行业的模板。
    """
    def __init__(self):
        self.client = client
        self.specific_outline = {}  # 原始特定行业大纲
        self.universal_template = {}  # 通用模板
        self.current_industry = ""  # 原模板的行业关键词
        self.target_industry = ""  # 目标行业关键词（如果有）
   
    def extract_from_template(self, template_path, current_industry=""):
        """
        从特定行业模板提取结构
        
        Parameters:
        -----------
        template_path : str
            报告模板文件路径
        current_industry : str, optional
            原模板所针对的行业关键词，用于识别和替换
        """
        self.current_industry = current_industry
        print(f"正在分析模板文件: {template_path}")
        print(f"原模板行业关键词: {current_industry}")
       
        try:
            # 读取模板文件
            with open(template_path, "r", encoding="utf-8") as f:
                if template_path.endswith('.json'):
                    # 如果是JSON文件，直接加载
                    try:
                        self.specific_outline = json.load(f)
                        print("JSON模板加载成功")
                    except json.JSONDecodeError:
                        print("JSON解析失败，将尝试作为文本处理")
                        f.seek(0)  # 重置文件指针
                        template_content = f.read()
                        # 提取结构
                        self._extract_structure(template_content)
                else:
                    # 普通文本文件
                    template_content = f.read()
                    # 提取结构
                    self._extract_structure(template_content)
            
            # 将特定行业模板泛化为通用模板
            self._generalize_template()
            
            return True
        except Exception as e:
            print(f"处理模板文件时出错: {str(e)}")
            return False
    
    def _extract_structure(self, content):
        """
        从模板内容中提取结构大纲
        """
        print("正在提取报告结构...")
        
        # 使用 LLM 提取结构
        prompt = f"""
请分析以下报告模板，提取其结构大纲和每个章节的主题：

1. 识别所有的一级标题(#)和二级标题(##)
2. 对每个标题下的内容进行分析，提取主要主题和关键点
3. 确保提取的结构是完整和准确的
4. 以JSON格式返回结构化的大纲，格式如下:

{{
  "main_title": "行业调研报告",
  "sections": [
    {{
      "title": "一级标题1",
      "subsections": [
        {{
          "title": "二级标题1",
          "theme": "该部分的主题概述",
          "search_terms": ["关键词1", "关键词2", "关键词3"]
        }},
        ...
      ]
    }},
    ...
  ]
}}

报告模板内容：

"""
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that analyzes document structure and extracts outlines."},
            {"role": "user", "content": prompt + content}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=4000,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            # 解析 JSON 结果
            try:
                self.specific_outline = json.loads(result)
                print("结构大纲提取成功!")
            except json.JSONDecodeError:
                print("JSON解析失败，尝试提取JSON部分...")
                # 尝试从响应中提取JSON部分
                json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
                if json_match:
                    try:
                        self.specific_outline = json.loads(json_match.group(1))
                        print("JSON提取成功!")
                    except:
                        print("提取的JSON部分解析失败")
                        self._create_default_outline()
                else:
                    print("无法提取JSON，使用默认大纲")
                    self._create_default_outline()
                    
        except Exception as e:
            print(f"调用API提取结构时出错: {str(e)}")
            self._create_default_outline()
    
    def _create_default_outline(self):
        """创建默认大纲结构"""
        self.specific_outline = {
            "main_title": "行业调研报告",
            "sections": [
                {
                    "title": "行业概况",
                    "subsections": [
                        {
                            "title": "行业定义与分类",
                            "theme": "分析行业的定义范围与分类标准",
                            "search_terms": ["行业定义", "分类标准", "细分领域"]
                        },
                        {
                            "title": "行业发展历程",
                            "theme": "分析行业的发展历史和阶段",
                            "search_terms": ["行业发展历史", "发展阶段", "关键里程碑"]
                        }
                    ]
                },
                {
                    "title": "市场规模与格局",
                    "subsections": [
                        {
                            "title": "市场规模",
                            "theme": "分析行业市场规模和增长趋势",
                            "search_terms": ["市场规模", "增长率", "市场份额"]
                        },
                        {
                            "title": "竞争格局",
                            "theme": "分析行业竞争状况",
                            "search_terms": ["市场竞争", "主要企业", "竞争策略"]
                        }
                    ]
                },
                {
                    "title": "行业趋势",
                    "subsections": [
                        {
                            "title": "技术趋势",
                            "theme": "分析行业技术发展趋势",
                            "search_terms": ["技术创新", "技术趋势", "新技术应用"]
                        },
                        {
                            "title": "政策环境",
                            "theme": "分析行业相关政策法规",
                            "search_terms": ["行业政策", "法规标准", "政府支持"]
                        }
                    ]
                }
            ]
        }
        print("已创建默认大纲结构")
    
    def _generalize_template(self):
        """
        将特定行业模板泛化为通用模板
        """
        print("正在生成通用模板...")
        
        # 使用 LLM 将特定行业模板转化为通用模板
        prompt = f"""
请将以下特定行业的报告大纲转化为通用行业报告模板，要求：

1. 将所有特定行业的术语和表述替换为通用表述
2. 使用{{industry}}作为行业名称的占位符
3. 保持原有的章节和子章节结构
4. 确保每个子章节都有theme和search_terms字段
5. 确保search_terms针对通用行业，并包括{{industry}}占位符
6. 保持原有的逻辑结构和分析框架

当前行业关键词：{self.current_industry if self.current_industry else "未指定"}

原始报告大纲：
{json.dumps(self.specific_outline, ensure_ascii=False, indent=2)}

请返回完整的通用模板JSON。
"""
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generalizes document templates."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=4000,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            # 解析 JSON 结果
            try:
                self.universal_template = json.loads(result)
                print("通用模板生成成功!")
            except json.JSONDecodeError:
                print("JSON解析失败，尝试提取JSON部分...")
                # 尝试从响应中提取JSON部分
                json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
                if json_match:
                    try:
                        self.universal_template = json.loads(json_match.group(1))
                        print("JSON提取成功!")
                    except:
                        print("提取的JSON部分解析失败")
                        # 如果无法从响应中提取有效的JSON，则使用一个简单的替换策略
                        self._basic_generalization()
                else:
                    print("无法提取JSON，使用简单替换策略")
                    self._basic_generalization()
                    
        except Exception as e:
            print(f"生成通用模板时出错: {str(e)}")
            # 使用简单替换策略作为备选方案
            self._basic_generalization()
    
    def _basic_generalization(self):
        """
        当LLM方法失败时的简单替换策略
        """
        print("使用简单替换策略生成通用模板...")
        
        # 复制原始大纲
        self.universal_template = json.loads(json.dumps(self.specific_outline))
        
        # 替换主标题
        if "main_title" in self.universal_template:
            self.universal_template["main_title"] = "{industry}行业调研报告"
        
        # 如果指定了当前行业关键词，尝试替换所有出现的地方
        if self.current_industry:
            # 递归替换函数
            def replace_industry(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, str):
                            obj[key] = value.replace(self.current_industry, "{industry}")
                        else:
                            replace_industry(value)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if isinstance(item, str):
                            obj[i] = item.replace(self.current_industry, "{industry}")
                        else:
                            replace_industry(item)
            
            # 应用替换
            replace_industry(self.universal_template)
        
        # 确保每个子章节都有theme和search_terms
        for section in self.universal_template.get("sections", []):
            for subsection in section.get("subsections", []):
                if "theme" not in subsection:
                    subsection["theme"] = f"分析{{industry}}行业中的{subsection['title']}"
                if "search_terms" not in subsection:
                    subsection["search_terms"] = [
                        f"{{industry}} {subsection['title']}",
                        f"{{industry}} 行业",
                        f"{{industry}} 分析",
                        f"{subsection['title']} 分析",
                        f"{{industry}} 市场"
                    ]
        
        print("基本通用模板生成完成")
    
    def generate_specific_outline(self, target_industry):
        """
        根据通用模板生成特定行业大纲
        
        Parameters:
        -----------
        target_industry : str
            目标行业关键词
        
        Returns:
        --------
        dict
            特定行业大纲
        """
        self.target_industry = target_industry
        
        if not self.universal_template:
            print("错误: 没有可用的通用模板")
            return None
        
        # 深复制通用模板
        specific_outline = json.loads(json.dumps(self.universal_template))
        
        # 递归替换函数
        def replace_placeholder(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str):
                        obj[key] = value.replace("{industry}", target_industry)
                    else:
                        replace_placeholder(value)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, str):
                        obj[i] = item.replace("{industry}", target_industry)
                    else:
                        replace_placeholder(item)
        
        # 应用替换
        replace_placeholder(specific_outline)
        
        print(f"已生成 {target_industry} 行业的具体大纲")
        return specific_outline
    
    def generate_section_prompts(self, outline=None):
        """
        为大纲中的章节生成提示词
        
        Parameters:
        -----------
        outline : dict, optional
            要生成提示词的大纲，默认使用当前加载的大纲
        
        Returns:
        --------
        dict
            章节提示词
        """
        if outline is None:
            if self.target_industry:
                outline = self.generate_specific_outline(self.target_industry)
            else:
                outline = self.specific_outline
        
        prompts = {}
        
        # 遍历大纲中的各章节
        for section_idx, section in enumerate(outline.get("sections", [])):
            section_title = section["title"]
            
            # 为每个子章节生成提示词
            for subsection_idx, subsection in enumerate(section.get("subsections", [])):
                subsection_title = subsection["title"]
                key = f"{section_idx+1}_{subsection_idx+1}_{subsection_title}"
                
                # 生成总结提示词模板
                summary_prompt = self._generate_summary_prompt(section_title, subsection_title,
                                                          subsection.get("theme", ""))
                
                # 存储提示词
                prompts[key] = {
                    "section": section_title,
                    "subsection": subsection_title,
                    "search_terms": subsection.get("search_terms", []),
                    "summary_prompt": summary_prompt
                }
                
                print(f"已生成 [{section_title} - {subsection_title}] 的提示词")
        
        print("所有章节提示词生成完成!")
        return prompts
    
    def _generate_summary_prompt(self, section_title, subsection_title, theme):
        """
        为特定章节生成总结提示词模板
        """
        keyword_placeholder = "{keyword}"
        
        prompt_template = f"""请对以下关于{keyword_placeholder}行业的"{section_title} - {subsection_title}"部分内容进行归纳总结，要求：

1. 语言专业流畅，逻辑清晰；
2. 保持行业专业性，确保术语使用准确；
3. 采用连贯的段落叙述方式，每段500-600字左右，每个自然段围绕一个核心观点展开，并确保段落间有清晰的逻辑关系和过渡；
4. 保留重要的数据、事实和案例作为论据，并在适当的地方使用表格展示关键数据；
5. 保留原有的引用标记[x]，确保学术严谨性；
6. 按时间顺序或逻辑关系组织内容，结构清晰；
7. 确保最终内容既有深度分析，又具实用价值；"""
        
        # 根据主题添加特定指导
        if theme:
            prompt_template += f"\n8. 重点关注以下主题：{theme}；"
        
        prompt_template += "\n9. 在最后部分添加一个总结段落，分析这一章节内容的整体情况和关键点；\n\n原始内容：\n{{content}}"
        
        return prompt_template
    
    def save_universal_template(self, output_path):
        """
        保存通用模板到JSON文件
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.universal_template, f, ensure_ascii=False, indent=2)
            print(f"通用模板已保存至：{output_path}")
            return True
        except Exception as e:
            print(f"保存通用模板时出错: {str(e)}")
            return False
    
    def save_specific_outline(self, output_path, industry=None):
        """
        保存特定行业大纲到JSON文件
        """
        try:
            if industry:
                outline = self.generate_specific_outline(industry)
            elif self.target_industry:
                outline = self.generate_specific_outline(self.target_industry)
            else:
                outline = self.specific_outline
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)
            print(f"行业大纲已保存至：{output_path}")
            return True
        except Exception as e:
            print(f"保存行业大纲时出错: {str(e)}")
            return False
    
    def save_prompts(self, output_path, industry=None):
        """
        保存章节提示词到JSON文件
        """
        try:
            if industry:
                outline = self.generate_specific_outline(industry)
                prompts = self.generate_section_prompts(outline)
            elif self.target_industry:
                outline = self.generate_specific_outline(self.target_industry)
                prompts = self.generate_section_prompts(outline)
            else:
                prompts = self.generate_section_prompts()
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(prompts, f, ensure_ascii=False, indent=2)
            print(f"章节提示词已保存至：{output_path}")
            return True
        except Exception as e:
            print(f"保存章节提示词时出错: {str(e)}")
            return False

def main():
    print("====== 报告模板通用化工具 ======")
    
    # 创建输出目录
    reports_dir = "reports"
    step0_dir = os.path.join(reports_dir, "step0")
    templates_dir = "templates"
    os.makedirs(step0_dir, exist_ok=True)
    os.makedirs(templates_dir, exist_ok=True)
    
    # 询问源模板文件路径
    default_template = os.path.join("templates", "original_template.json")
    template_path = input(f"请输入源报告模板文件路径（默认: {default_template}）: ").strip()
    if not template_path:
        template_path = default_template
    
    # 询问源模板的行业关键词
    current_industry = input("请输入源模板的行业关键词（如：核磁共振、MRI等，用于识别和替换）: ").strip()
    
    # 初始化模板通用化工具
    generalizer = TemplateGeneralizer()
    
    # 从源模板提取结构
    if not os.path.exists(template_path):
        print(f"错误: 模板文件 {template_path} 不存在")
        return
    
    if not generalizer.extract_from_template(template_path, current_industry):
        print("从源模板提取结构失败，程序终止。")
        return
    
    # 保存通用模板
    universal_template_path = os.path.join(templates_dir, "universal_template.json")
    generalizer.save_universal_template(universal_template_path)
    
    # 询问是否需要立即生成特定行业报告
    generate_specific = input("是否需要立即为特定行业生成报告大纲？(y/n): ").strip().lower()
    
    if generate_specific == 'y':
        # 询问目标行业关键词
        target_industry = input("请输入目标行业关键词（如：培养皿、医疗器械等）: ").strip()
        
        if target_industry:
            # 保存目标行业大纲
            outline_path = os.path.join(step0_dir, "report_outline.json")
            generalizer.save_specific_outline(outline_path, target_industry)
            
            # 保存目标行业提示词
            prompts_path = os.path.join(step0_dir, "section_prompts.json")
            generalizer.save_prompts(prompts_path, target_industry)
            
            print("\n====== 特定行业报告结构生成完成 ======")
            print(f"1. {target_industry}行业大纲已保存至: {outline_path}")
            print(f"2. {target_industry}行业章节提示词已保存至: {prompts_path}")
    
    print("\n====== 通用模板生成完成 ======")
    print(f"通用报告模板已保存至: {universal_template_path}")
    print("您可以使用此通用模板为任何行业生成报告，只需替换{industry}占位符。")
    
    print("\n要为新行业生成报告，请运行以下命令：")
    print(f"python {os.path.basename(__file__)} --industry 行业名称 --template {universal_template_path}")

if __name__ == "__main__":
    import argparse
    
    # 检查是否有命令行参数
    if len(os.sys.argv) > 1:
        parser = argparse.ArgumentParser(description="从通用模板生成特定行业报告")
        parser.add_argument("--industry", required=True, help="目标行业关键词")
        parser.add_argument("--template", default=os.path.join("templates", "universal_template.json"), 
                           help="通用模板路径")
        parser.add_argument("--output-dir", default=os.path.join("reports", "step0"),
                           help="输出目录")
        
        args = parser.parse_args()
        
        # 确保输出目录存在
        os.makedirs(args.output_dir, exist_ok=True)
        
        # 初始化工具
        generalizer = TemplateGeneralizer()
        
        # 加载通用模板
        if generalizer.extract_from_template(args.template):
            # 保存目标行业大纲
            outline_path = os.path.join(args.output_dir, "report_outline.json")
            generalizer.save_specific_outline(outline_path, args.industry)
            
            # 保存目标行业提示词
            prompts_path = os.path.join(args.output_dir, "section_prompts.json")
            generalizer.save_prompts(prompts_path, args.industry)
            
            print(f"\n已成功为 {args.industry} 行业生成报告结构")
            print(f"报告大纲: {outline_path}")
            print(f"章节提示词: {prompts_path}")
        else:
            print(f"无法加载通用模板: {args.template}")
    else:
        main()