import os
import time
import re
import json
# 在导入matplotlib之前设置后端为非交互式
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免tkinter相关错误
import matplotlib.pyplot as plt
import numpy as np
from openai import OpenAI

# Make sure the environment variable DS_API_KEY is set, otherwise replace it with your API Key
API_KEY = os.environ.get("DS_API_KEY", "")

# Initialize deepseek client
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

class ContentProcessor:
    """
    Summarize and refine content using DeepSeek's chat completion API,
    with reflection process to reduce hallucinations.
    Includes data visualization functionality to extract and visualize data from text.
    """
    def __init__(self):
        self.client = client

    def extract_sub_title(self, content, filename):
        """
        Try to extract heading from Markdown content;
        If none exists, use the filename (without extension) as the subsection title.
        """
        # First try to extract second-level heading (##)
        match = re.search(r'^##\s*(.+)', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # If no second-level heading, try to extract first-level heading (#)
        match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
            
        # If none found, extract from filename
        parts = os.path.splitext(filename)[0].split('_')
        if len(parts) >= 3:
            # Assuming filename format is: 1_1_section_name.md
            return ' '.join(parts[2:])
        return os.path.splitext(filename)[0]

    def extract_prompt_from_file(self, filename, prompts_dir):
        """
        Extract custom prompts from prompt file, if it exists
        """
        prompt_filename = f"{os.path.splitext(filename)[0]}_prompt.txt"
        prompt_path = os.path.join(prompts_dir, prompt_filename)
        
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading prompt file: {str(e)}")
        
        return None

    def extract_data_for_visualization(self, content, sub_title, keyword):
        """
        Extract data suitable for visualization from the content with enhanced support
        for multiple chart types and additional data series
        """
        prompt = f"""Please analyze the following content about the "{sub_title}" of the {keyword} industry, and extract data suitable for visualization:

1. Identify ALL numerical data in the content that could be visualized, including data in tables, statistics mentioned in the text, trends, comparisons, and distributions
2. For each data set, choose the most appropriate chart type from the following options:
   - bar: For comparing individual data points
   - horizontal_bar: For comparing categories with long names
   - stacked_bar: For showing composition of categories
   - line: For showing trends over time or continuous data
   - area: For emphasizing magnitude of trends
   - pie: For showing composition of a whole (use only when 3-7 categories)
   - donut: Similar to pie but with better visual appeal
   - scatter: For showing correlation between variables
   - bubble: For showing three dimensions of data
   - radar: For comparing multiple variables at once

3. Extract the data and return in this enhanced JSON format:

```json
[
  {{
    "chart_title": "详细的图表标题（中文）",
    "chart_type": "chart_type",
    "x_label": "X轴标签（中文）",
    "y_label": "Y轴标签（中文）",
    "data": {{
      "labels": ["标签1", "标签2", ...],
      "values": [value1, value2, ...],
      "additional_series": [
        {{
          "name": "系列名称1",
          "values": [value1, value2, ...]
        }},
        {{
          "name": "系列名称2",
          "values": [value1, value2, ...]
        }}
      ],
      "sizes": [size1, size2, ...] // Optional, for bubble or scatter charts
    }}
  }},
  // There can be multiple charts
]
```

IMPORTANT GUIDELINES:
1. Ensure ALL chart titles, labels, and series names are in Chinese
2. Extract ONLY data that actually exists in the text, do not fabricate data
3. Choose the most suitable chart type for each data set
4. If there's time-series data or comparisons across categories, they are excellent candidates for visualization
5. If there is no suitable data for visualization, return an empty array []
6. Include additional data series when multiple related sets of data are present
7. Make sure all numeric values are properly extracted as numbers, not strings

Content:
{content}
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in data extraction and visualization, with expertise in Chinese language data visualization."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model="deepseek-reasoner",
                messages=messages,
                max_tokens=3000,
                temperature=0.3,
                stream=False
            )
            visualization_data = response.choices[0].message.content
            
            # Extract JSON portion
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', visualization_data)
            if json_match:
                json_str = json_match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Unable to parse JSON data: {json_str}")
                    return []
            else:
                # If no code block markers, try parsing the entire response
                try:
                    return json.loads(visualization_data)
                except json.JSONDecodeError:
                    print(f"Unable to parse JSON data: {visualization_data}")
                    return []
        except Exception as e:
            print(f"Error extracting visualization data: {str(e)}")
            return []

    def generate_charts(self, visualization_data, output_dir, base_filename):
        """
        Generate charts based on extracted data with improved Chinese font support
        and variety of chart types
        """
        charts_info = []
        
        # Setup Chinese font support
        import matplotlib.font_manager as fm
        # Try to find a Chinese font in the system
        chinese_fonts = [
            'SimHei', 'Microsoft YaHei', 'STSong', 'STFangsong', 'FangSong', 'KaiTi', 
            'SimSun', 'NSimSun', 'STXihei', 'STZhongsong', 'STKaiti', 'STLiti', 
            'STHupo', 'STCaiyun', 'STXingkai', 'STXinwei'
        ]
        
        chinese_font = None
        for font in chinese_fonts:
            if any(font.lower() in f.lower() for f in fm.findSystemFonts()):
                chinese_font = font
                break
        
        if not chinese_font:
            # If no Chinese font found, use a default available font
            chinese_font = 'DejaVu Sans'
            print("Warning: No specific Chinese font found. Using default font.")
        
        # Set global font
        plt.rcParams['font.family'] = chinese_font
        plt.rcParams['axes.unicode_minus'] = False
        
        # Create color schemes for different chart types
        color_schemes = {
            "bar": plt.cm.Blues,
            "line": plt.cm.Oranges,
            "pie": plt.cm.Greens,
            "scatter": plt.cm.Purples,
            "horizontal_bar": plt.cm.Reds,
            "stacked_bar": plt.cm.YlOrBr,
            "area": plt.cm.PuBu,
            "bubble": plt.cm.RdYlBu,
            "radar": plt.cm.tab10,
            "donut": plt.cm.Pastel1
        }
        
        for i, chart_data in enumerate(visualization_data):
            try:
                chart_type = chart_data.get("chart_type", "bar").lower()
                chart_title = chart_data.get("chart_title", f"图表 {i+1}")
                x_label = chart_data.get("x_label", "")
                y_label = chart_data.get("y_label", "")
                
                labels = chart_data.get("data", {}).get("labels", [])
                values = chart_data.get("data", {}).get("values", [])
                
                # Handle additional data series if available
                additional_series = chart_data.get("data", {}).get("additional_series", [])
                
                if not labels or not values or len(labels) != len(values):
                    print(f"Chart '{chart_title}' data incomplete or mismatched, skipping generation")
                    continue
                
                # Create figure with appropriate font
                plt.figure(figsize=(12, 8))
                fig = plt.gcf()
                ax = plt.gca()
                
                # Get color map based on chart type
                cmap = color_schemes.get(chart_type, plt.cm.Blues)
                
                if chart_type == "bar":
                    bars = plt.bar(labels, values, color=cmap(np.linspace(0.3, 0.8, len(values))))
                    # Add value labels on top of bars
                    for bar in bars:
                        height = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                                 f'{height:.1f}', ha='center', va='bottom', fontsize=9)
                
                elif chart_type == "horizontal_bar":
                    bars = plt.barh(labels, values, color=cmap(np.linspace(0.3, 0.8, len(values))))
                    # Add value labels at end of bars
                    for bar in bars:
                        width = bar.get_width()
                        plt.text(width + max(values)*0.01, bar.get_y() + bar.get_height()/2.,
                                 f'{width:.1f}', ha='left', va='center', fontsize=9)
                
                elif chart_type == "stacked_bar":
                    if additional_series:
                        bottom = np.zeros(len(labels))
                        for j, series in enumerate(additional_series):
                            series_values = series.get("values", [])
                            series_name = series.get("name", f"系列 {j+1}")
                            if len(series_values) == len(labels):
                                plt.bar(labels, series_values, bottom=bottom, 
                                       label=series_name, color=cmap(0.3 + 0.5*j/len(additional_series)))
                                bottom += np.array(series_values)
                        plt.legend(loc='best', fontsize=10)
                    else:
                        plt.bar(labels, values, color=cmap(np.linspace(0.3, 0.8, len(values))))
                
                elif chart_type == "line":
                    # Use markers and line style
                    plt.plot(labels, values, marker='o', linestyle='-', linewidth=2.5, 
                            color=cmap(0.6), markersize=8, markerfacecolor=cmap(0.8))
                    # Add value labels above points
                    for i, (x, y) in enumerate(zip(labels, values)):
                        plt.text(i, y + max(values)*0.02, f'{y:.1f}', ha='center', fontsize=9)
                    
                    # Handle multiple lines if additional series exist
                    if additional_series:
                        for j, series in enumerate(additional_series):
                            series_values = series.get("values", [])
                            series_name = series.get("name", f"系列 {j+1}")
                            if len(series_values) == len(labels):
                                plt.plot(labels, series_values, marker='s', linestyle='--', 
                                       label=series_name, color=cmap(0.3 + 0.5*j/len(additional_series)))
                        plt.legend(loc='best', fontsize=10)
                
                elif chart_type == "area":
                    plt.fill_between(range(len(labels)), values, alpha=0.5, color=cmap(0.6))
                    plt.plot(range(len(labels)), values, 'o-', color=cmap(0.8))
                    plt.xticks(range(len(labels)), labels)
                
                elif chart_type == "pie":
                    # Enhanced pie chart with percentage and value display
                    wedges, texts, autotexts = plt.pie(
                        values, 
                        labels=None,  # We'll add custom legend
                        autopct='%1.1f%%',
                        startangle=90,
                        colors=[cmap(0.2 + 0.6*i/len(values)) for i in range(len(values))],
                        textprops={'fontsize': 10}
                    )
                    # Enhance text visibility
                    for autotext in autotexts:
                        autotext.set_color('white')
                        autotext.set_fontsize(9)
                    
                    # Add legend with labels
                    plt.legend(wedges, labels, title="分类", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                    plt.axis('equal')
                
                elif chart_type == "donut":
                    # Create a donut chart (pie with a hole)
                    wedges, texts, autotexts = plt.pie(
                        values, 
                        labels=None,
                        autopct='%1.1f%%',
                        startangle=90,
                        colors=[cmap(0.2 + 0.6*i/len(values)) for i in range(len(values))],
                        textprops={'fontsize': 10}
                    )
                    # Make a hole in the center
                    centre_circle = plt.Circle((0,0), 0.70, fc='white')
                    fig.gca().add_artist(centre_circle)
                    
                    # Add legend with labels
                    plt.legend(wedges, labels, title="分类", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                    plt.axis('equal')
                
                elif chart_type == "scatter":
                    # Create scatter plot with varying point sizes if available
                    sizes = chart_data.get("data", {}).get("sizes", [50] * len(values))
                    if len(sizes) != len(values):
                        sizes = [50] * len(values)
                    
                    scatter = plt.scatter(
                        range(len(labels)), 
                        values, 
                        s=sizes,
                        c=np.arange(len(labels)), 
                        cmap=cmap, 
                        alpha=0.7
                    )
                    plt.xticks(range(len(labels)), labels)
                    
                    # Add a colorbar if there are enough data points
                    if len(values) > 3:
                        plt.colorbar(scatter)
                
                elif chart_type == "bubble":
                    # Bubble chart with varying sizes
                    sizes = chart_data.get("data", {}).get("sizes", [v*10 for v in values])
                    if len(sizes) != len(values):
                        sizes = [v*10 for v in values]
                    
                    x_pos = np.arange(len(labels))
                    plt.scatter(x_pos, values, s=sizes, alpha=0.6, 
                               c=x_pos, cmap=cmap, edgecolors='black')
                    plt.xticks(x_pos, labels)
                
                elif chart_type == "radar":
                    # Implement radar chart (polar plot)
                    from matplotlib.path import Path
                    from matplotlib.spines import Spine
                    from matplotlib.projections.polar import PolarAxes
                    from matplotlib.projections import register_projection
                    
                    # Convert to radar coordinates
                    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
                    values += values[:1]  # Close the loop
                    angles += angles[:1]  # Close the loop
                    
                    # Create radar plot
                    ax = plt.subplot(111, polar=True)
                    plt.xticks(angles[:-1], labels, fontsize=10)
                    ax.plot(angles, values, 'o-', linewidth=2)
                    ax.fill(angles, values, alpha=0.25)
                    ax.set_rlabel_position(0)
                    
                    # Add value labels
                    for i, (angle, value) in enumerate(zip(angles[:-1], values[:-1])):
                        plt.text(angle, value*1.1, f'{value:.1f}', ha='center', va='center')
                
                else:
                    # Default to bar chart
                    plt.bar(labels, values, color=cmap(np.linspace(0.3, 0.8, len(values))))
                
                # Set title and labels with enhanced styling
                plt.title(chart_title, fontsize=16, fontweight='bold', pad=20)
                
                if chart_type not in ["pie", "donut", "radar"]:
                    plt.xlabel(x_label, fontsize=12, labelpad=10)
                    plt.ylabel(y_label, fontsize=12, labelpad=10)
                    
                    # Rotate x-axis labels for better readability
                    if chart_type != "horizontal_bar":
                        plt.xticks(rotation=45, ha='right', fontsize=10)
                
                # Grid for better readability (except for pie and donut)
                if chart_type not in ["pie", "donut"]:
                    plt.grid(True, linestyle='--', alpha=0.7)
                
                # Add a subtle border
                for spine in plt.gca().spines.values():
                    spine.set_visible(True)
                    spine.set_color('gray')
                    spine.set_linewidth(0.5)
                
                # Adjust layout
                plt.tight_layout()
                
                # Save chart with higher DPI
                chart_filename = f"{base_filename}_chart_{i+1}.png"
                chart_path = os.path.join(output_dir, "charts", chart_filename)
                os.makedirs(os.path.dirname(chart_path), exist_ok=True)
                plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                plt.close()
                
                charts_info.append({
                    "title": chart_title,
                    "type": chart_type,
                    "path": chart_path,
                    "markdown_ref": f"![{chart_title}](charts/{chart_filename})"
                })
                
                print(f"Generated chart: {chart_title} -> {chart_path}")
            except Exception as e:
                print(f"Error generating chart '{chart_data.get('chart_title', f'Chart {i+1}')}': {str(e)}")
        
        return charts_info

    def generate_reflection(self, content, sub_title, keyword):
        """
        Reflect on the generated content, checking factual accuracy, logical coherence, etc.
        """
        prompt = f"""Please evaluate the following content about the "{sub_title}" of the {keyword} industry, checking for:

1. Are there any factual errors or inaccurate information?
2. Are there any logical inconsistencies or contradictions?
3. Are there any overly vague or ambiguous statements?
4. Are there any claims lacking clear references or supporting evidence?
5. Are there any knowledge gaps or important information missing?
6. Are there any data points that would be better presented as charts rather than text descriptions?

For each issue found, please indicate the specific location and suggest how it could be improved. If the content quality is good, please also highlight its strengths.

Content:
{content}
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in critical analysis."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=2000,
                temperature=0.5,
                stream=False
            )
            reflection = response.choices[0].message.content
            return reflection
        except Exception as e:
            print(f"Error generating reflection: {str(e)}")
            return "Reflection generation failed."

    def optimize_content(self, content, reflection, sub_title, keyword, charts_info=None):
        """
        Optimize content based on reflection results, and insert chart references at appropriate locations
        with improved guidance for chart placement
        """
        charts_prompt = ""
        if charts_info and len(charts_info) > 0:
            charts_prompt = "\n\n我们已经根据内容生成了以下图表。请在优化后的内容中的最恰当位置插入这些图表引用：\n\n"
            for chart in charts_info:
                charts_prompt += f"- {chart['title']} ({chart['type']} 类型图表): 插入 `{chart['markdown_ref']}` 在相关数据或描述附近\n"
        
        prompt = f"""请根据以下反馈优化关于"{sub_title}"的{keyword}行业内容：

原始内容:
{content}

反馈:
{reflection}{charts_prompt}

请全面改进内容，重点解决反馈中指出的问题，确保:
1. 修正所有事实错误和不准确信息
2. 确保逻辑连贯性和论证一致性
3. 用具体、清晰的内容替换模糊的陈述
4. 添加数据来源和支持证据以增强可信度
5. 填补知识空白，添加重要的缺失信息
6. 保持专业性和可读性
7. 在最合适的位置插入图表引用（如果有）

注意事项:
- 图表应该放在相关数据讨论的附近，不要集中放在一起
- 每个图表前后应有相关说明或分析，帮助读者理解图表展示的要点
- 图表引用后应该有1-2句对图表内容的简短总结或补充说明
- 图表不应打断文章的逻辑流程，应该作为对文本内容的补充
- 如果文章中提到了某个数据趋势或比较，相关图表应该放在该段落之后

请提供完整的优化内容，而不仅仅是修改列表。不要在开头列出修改项或总结，也不要包含"以下是优化后的内容"等过渡语句。直接从正文内容开始。
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in content optimization, with expertise in integrating data visualizations into reports."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model="deepseek-reasoner",
                messages=messages,
                max_tokens=5000,
                temperature=0.7,
                stream=False
            )
            optimized = response.choices[0].message.content
            return optimized
        except Exception as e:
            print(f"Error optimizing content: {str(e)}")
            return content  # If optimization fails, return original content

    def summarize_content(self, content, sub_title, keyword, custom_prompt=None):
        """
        Generate a summary based on the original content,
        ensuring clear structure, professionalism, and appropriate use of tables for data.
        """
        # Use custom prompt or default prompt
        if custom_prompt:
            prompt = custom_prompt.replace("{keyword}", keyword).replace("{content}", content)
        else:
            prompt = f"""Please summarize the following content about the "{sub_title}" of the {keyword} industry, ensuring:

1. Professional and fluid language with clear logic
2. Maintain industry professionalism with accurate terminology
3. Use cohesive paragraphs of about 500-600 words each, with each paragraph focused on a core concept, and ensure clear logical relationships and transitions between paragraphs
4. Retain important data, facts, and cases as arguments, and use tables to present key data where appropriate
5. Retain original citation markers [x] to ensure academic rigor
6. Organize content by chronological order or logical relationship with clear structure
7. Ensure the final content has both depth of analysis and practical value
8. Add a concluding paragraph analyzing the overall situation and key points of this section

Original content:

{content}
"""

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model="deepseek-reasoner",
                messages=messages,
                max_tokens=5000,
                temperature=0.7,
                stream=False
            )
            summary = response.choices[0].message.content
            return summary
        except Exception as e:
            print(f"Error calling DeepSeek API: {str(e)}")
            return content

def load_section_prompts():
    """
    Load section prompts generated from step0
    """
    # 从环境变量中获取step0目录路径，如果没有则使用默认路径
    step0_dir = os.environ.get("REPORT_STEP0_DIR", os.path.join("reports", "step0"))
    
    prompts_path = os.path.join(step0_dir, "section_prompts.json")
    
    if os.path.exists(prompts_path):
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading section prompts: {str(e)}")
    
    return {}

def find_prompt_for_section(section_prompts, filename):
    """
    Find the prompt for the corresponding section
    """
    parts = os.path.splitext(filename)[0].split('_')
    if len(parts) >= 3:
        section_key = '_'.join(parts)
        if section_key in section_prompts:
            return section_prompts[section_key]["summary_prompt"]
    
    # Try to find by matching partial title
    section_title = '_'.join(parts[2:]) if len(parts) >= 3 else ''
    for key, value in section_prompts.items():
        if section_title.lower() in value["subsection"].lower():
            return value["summary_prompt"]
    
    return None

def main():
    keyword = input("Please enter the industry keyword for the research report (consistent with step1): ").strip()
    
    # 从环境变量中读取目录路径，如果没有则使用默认路径
    step1_dir = os.environ.get("REPORT_STEP1_DIR", os.path.join("reports", "step1"))
    step2_dir = os.environ.get("REPORT_STEP2_DIR", os.path.join("reports", "step2"))
    
    input_dir = step1_dir
    prompts_dir = os.path.join(input_dir, "prompts")
    output_dir = step2_dir
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "charts"), exist_ok=True)
   
    processor = ContentProcessor()
    section_prompts = load_section_prompts()
   
    # Process Markdown files generated in step1
    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            input_path = os.path.join(input_dir, filename)
            with open(input_path, "r", encoding="utf-8") as f:
                original_content = f.read()
           
            # Extract subsection title
            sub_title = processor.extract_sub_title(original_content, filename)
            print(f"\nSummarizing: {sub_title}")
            
            # Find custom prompt
            custom_prompt = processor.extract_prompt_from_file(filename, prompts_dir)
            if not custom_prompt:
                custom_prompt = find_prompt_for_section(section_prompts, filename)
                
            # Generate summary
            summary = processor.summarize_content(original_content, sub_title, keyword, custom_prompt)
            
            print("Summary generation complete, performing reflection evaluation...")
            
            # Perform reflection
            reflection = processor.generate_reflection(summary, sub_title, keyword)
            
            # Save reflection results
            reflection_filename = f"{os.path.splitext(filename)[0]}_reflection.md"
            reflection_path = os.path.join(output_dir, reflection_filename)
            with open(reflection_path, "w", encoding="utf-8") as f:
                f.write(f"# {sub_title} - Reflection Evaluation\n\n{reflection}")
            print(f"Saved reflection evaluation to: {reflection_path}")
            
            # Extract visualization data and generate charts
            print("Extracting data and generating charts...")
            visualization_data = processor.extract_data_for_visualization(summary, sub_title, keyword)
            base_filename = os.path.splitext(filename)[0]
            charts_info = processor.generate_charts(visualization_data, output_dir, base_filename)
            
            print("Optimizing content based on reflection...")
            
            # Optimize content based on reflection, and insert chart references
            optimized = processor.optimize_content(summary, reflection, sub_title, keyword, charts_info)
            
            # Save optimized content
            optimized_filename = f"{os.path.splitext(filename)[0]}_optimized.md"
            optimized_path = os.path.join(output_dir, optimized_filename)
            with open(optimized_path, "w", encoding="utf-8") as f:
                f.write(optimized)
            print(f"Saved optimized content to: {optimized_path}")
            
            # Also save original summary (for comparison)
            summary_filename = f"{os.path.splitext(filename)[0]}_summary.md"
            summary_path = os.path.join(output_dir, summary_filename)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            print(f"Saved original summary to: {summary_path}")
            
            # Save visualization data
            if visualization_data:
                viz_data_filename = f"{os.path.splitext(filename)[0]}_visualization_data.json"
                viz_data_path = os.path.join(output_dir, "charts", viz_data_filename)
                with open(viz_data_path, "w", encoding="utf-8") as f:
                    json.dump(visualization_data, f, ensure_ascii=False, indent=2)
                print(f"Saved visualization data to: {viz_data_path}")
            
            time.sleep(1)
    
    print("\n====== Content Summarization and Optimization Complete ======")
    print(f"All content saved to: {output_dir}")
    print(f"Generated charts saved to: {os.path.join(output_dir, 'charts')}")
    print("Please run step3.py to compile the final report.")

if __name__ == "__main__":
    main()