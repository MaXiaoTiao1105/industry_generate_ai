import os
import sys
import json
import time
import logging
import builtins
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ReportConfig:
    """报告生成配置类"""
    industry: str  # 行业关键词
    api_key: str  # API密钥
    zhipu_api_key: Optional[str] = None  # 智谱API密钥
    output_dir: str = "reports"  # 输出目录
    template_path: Optional[str] = None  # 可选的模板文件路径
    current_industry: str = ""  # 模板中的当前行业（如果使用模板）

class IndustryReportGenerator:
    """行业报告生成器主类"""
    
    def __init__(self, config: ReportConfig):
        """
        初始化报告生成器
        
        Args:
            config: ReportConfig对象，包含必要的配置信息
        """
        self.config = config
        self.setup_environment()
        
        # 设置API密钥
        os.environ["DS_API_KEY"] = config.api_key
        if config.zhipu_api_key:
            os.environ["ZHIPU_API_KEY"] = config.zhipu_api_key  # 使用智谱API密钥
        
        # 导入步骤模块
        try:
            import step0
            import step1_enhance as step1
            import step2 as step2
            import step3
            
            self.step0 = step0
            self.step1 = step1
            self.step2 = step2
            self.step3 = step3
        except ImportError as e:
            logger.error(f"导入步骤模块失败: {str(e)}")
            raise
    
    def setup_environment(self):
        """设置必要的目录结构"""
        # 创建主输出目录
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        # 创建各步骤的子目录
        self.step0_dir = os.path.join(self.config.output_dir, "step0")
        self.step1_dir = os.path.join(self.config.output_dir, "step1")
        self.step2_dir = os.path.join(self.config.output_dir, "step2")
        self.final_dir = os.path.join(self.config.output_dir, "final")
        
        os.makedirs(self.step0_dir, exist_ok=True)
        os.makedirs(self.step1_dir, exist_ok=True)
        os.makedirs(self.step2_dir, exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        
        # 创建模板目录
        os.makedirs("templates", exist_ok=True)
    
    def generate_report(self, callback: Optional[callable] = None, output_format: str = "markdown") -> Dict[str, Any]:
        """
        生成完整的行业报告
        
        Args:
            callback: 可选的回调函数，用于报告进度
            output_format: 输出格式，可选值为"markdown"或"pdf"
            
        Returns:
            Dict包含生成报告的相关信息
        """
        start_time = time.time()
        result = {
            "success": False,
            "error": None,
            "output_files": {},
            "execution_time": 0,
            "industry": self.config.industry
        }
        
        # 保存原始的input函数
        original_input = builtins.input
        
        try:
            # 步骤0：生成报告模板
            if callback:
                callback("正在生成报告模板...", 0)
            
            logger.info("开始执行步骤0：生成报告模板")
            generalizer = self.step0.TemplateGeneralizer()
            
            if self.config.template_path:
                generalizer.extract_from_template(
                    self.config.template_path,
                    self.config.current_industry
                )
            else:
                # 使用默认模板
                generalizer._create_default_outline()
            
            # 生成特定行业大纲
            outline = generalizer.generate_specific_outline(self.config.industry)
            prompts = generalizer.generate_section_prompts(outline)
            
            # 保存大纲和提示词到step0目录
            outline_path = os.path.join(self.step0_dir, "report_outline.json")
            prompts_path = os.path.join(self.step0_dir, "section_prompts.json")
            
            with open(outline_path, "w", encoding="utf-8") as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)
            with open(prompts_path, "w", encoding="utf-8") as f:
                json.dump(prompts, f, ensure_ascii=False, indent=2)
            
            result["output_files"]["outline"] = outline_path
            result["output_files"]["prompts"] = prompts_path
            
            # 替换input函数为返回行业关键词的lambda函数
            builtins.input = lambda _: self.config.industry
            
            # 步骤1：收集内容
            if callback:
                callback("正在收集行业内容...", 25)
            
            logger.info("开始执行步骤1：收集行业内容")
            # 设置环境变量，确保step1使用正确的目录
            os.environ["REPORT_STEP0_DIR"] = self.step0_dir
            os.environ["REPORT_STEP1_DIR"] = self.step1_dir
            self.step1.main()
            
            # 步骤2：内容优化
            if callback:
                callback("正在优化内容...", 50)
            
            logger.info("开始执行步骤2：内容优化")
            # 设置环境变量，确保step2使用正确的目录
            os.environ["REPORT_STEP0_DIR"] = self.step0_dir
            os.environ["REPORT_STEP1_DIR"] = self.step1_dir
            os.environ["REPORT_STEP2_DIR"] = self.step2_dir
            self.step2.main()
            
            # 步骤3：生成最终报告
            if callback:
                callback("正在生成最终报告...", 75)
            
            logger.info("开始执行步骤3：生成最终报告")
            # 设置环境变量，确保step3使用正确的目录
            os.environ["REPORT_STEP0_DIR"] = self.step0_dir
            os.environ["REPORT_STEP2_DIR"] = self.step2_dir
            os.environ["REPORT_FINAL_DIR"] = self.final_dir
            self.step3.merge_report()
            
            # 最终报告路径
            final_report_path = os.path.join(
                self.final_dir,
                f"{self.config.industry}行业调研报告_最终版.md"
            )
            
            result["output_files"]["final_report"] = final_report_path
            
            # 如果需要PDF格式，使用pandoc转换
            if output_format == "pdf":
                if callback:
                    callback("正在生成PDF文件...", 90)
                
                logger.info("开始生成PDF文件")
                pdf_path = final_report_path.replace('.md', '.pdf')
                
                try:
                    # 使用pandoc转换为PDF
                    pandoc_cmd = [
                        "pandoc", 
                        final_report_path, 
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
                    import subprocess
                    process = subprocess.run(
                        pandoc_cmd,
                        capture_output=True,
                        text=True
                    )
                    
                    if process.returncode != 0:
                        logger.error(f"PDF转换失败: {process.stderr}")
                    elif os.path.exists(pdf_path):
                        logger.info(f"PDF转换成功: {pdf_path}")
                        result["output_files"]["final_report_pdf"] = pdf_path
                    else:
                        logger.warning(f"PDF文件未生成: {pdf_path}")
                except Exception as e:
                    logger.error(f"PDF转换过程中出错: {str(e)}")
                    # 继续执行，不因PDF转换失败而中断整个流程
            
            result["success"] = True
            
            if callback:
                callback("报告生成完成！", 100)
            
        except Exception as e:
            error_msg = f"生成报告时出错: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
        finally:
            # 恢复原始的input函数
            builtins.input = original_input
            result["execution_time"] = time.time() - start_time
        
        return result

def generate_report(
    industry: str,
    api_key: str,
    zhipu_api_key: str = None,  # 添加智谱API密钥参数
    output_dir: str = "reports",
    template_path: Optional[str] = None,
    current_industry: str = "",
    callback: Optional[callable] = None,
    output_format: str = "markdown"  # 添加输出格式参数
) -> Dict[str, Any]:
    """
    生成行业报告的便捷函数
    
    Args:
        industry: 行业关键词
        api_key: DeepSeek API密钥
        zhipu_api_key: 智谱API密钥
        output_dir: 输出目录
        template_path: 可选的模板文件路径
        current_industry: 模板中的当前行业（如果使用模板）
        callback: 可选的进度回调函数
        output_format: 输出格式，可选值为"markdown"或"pdf"
    
    Returns:
        Dict包含生成报告的相关信息
    """
    config = ReportConfig(
        industry=industry,
        api_key=api_key,
        zhipu_api_key=zhipu_api_key,  # 添加智谱API密钥
        output_dir=output_dir,
        template_path=template_path,
        current_industry=current_industry
    )
    
    generator = IndustryReportGenerator(config)
    return generator.generate_report(callback, output_format)

def main():
    """命令行入口函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="行业报告生成工具")
    parser.add_argument("industry", help="行业关键词")
    parser.add_argument("api_key", help="API密钥")
    parser.add_argument("--output-dir", default="reports", help="输出目录")
    parser.add_argument("--template", help="模板文件路径")
    parser.add_argument("--current-industry", help="模板中的当前行业")
    
    args = parser.parse_args()
    
    def progress_callback(message: str, percentage: int):
        print(f"{message} ({percentage}%)")
    
    result = generate_report(
        industry=args.industry,
        api_key=args.api_key,
        output_dir=args.output_dir,
        template_path=args.template,
        current_industry=args.current_industry,
        callback=progress_callback
    )
    
    if result["success"]:
        print("\n报告生成成功！")
        print(f"最终报告保存在: {result['output_files']['final_report']}")
        print(f"总执行时间: {result['execution_time']:.2f} 秒")
    else:
        print(f"\n报告生成失败: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main() 