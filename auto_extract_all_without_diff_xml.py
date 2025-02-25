import os
import time
import logging
from typing import Optional
import psutil
from tqdm import tqdm

# 导入其他脚本
from 自动提取版本xml import VersionMonitor
from 对比xml import load_xml, compare_xml, write_new_xml
from 根据版本xml下载对应swf import SwfDownloader
from ffdec_export import FFDecExporter

class AutoExtractor:
    def __init__(self):
        """初始化自动提取器喵~"""
        self.setup_logging()
        self.ffdec_path = ""
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "output")
        self.setup_system_info()
        self.old_xml_path = ""
        self.new_xml_path = ""

    def setup_system_info(self):
        """设置系统信息和优化线程配置喵~"""
        # 获取CPU信息
        self.cpu_count = psutil.cpu_count(logical=True)
        self.physical_cores = psutil.cpu_count(logical=False)
        self.cpu_percent = psutil.cpu_percent(interval=1)
        
        # 获取内存信息
        memory = psutil.virtual_memory()
        self.total_memory = memory.total / (1024**3)  # GB
        self.memory_percent = memory.percent
        
        # 根据系统负载动态调整线程数
        if self.cpu_percent < 30:  # CPU负载低
            self.max_workers = self.cpu_count * 2
        elif self.cpu_percent < 60:  # CPU负载中等
            self.max_workers = self.cpu_count
        else:  # CPU负载高
            self.max_workers = self.physical_cores
        
        # 根据内存使用情况调整
        if self.memory_percent > 80:  # 内存使用率高
            self.max_workers = min(self.max_workers, self.physical_cores)
        
        # 记录系统信息
        logging.info(f"系统信息喵~:")
        logging.info(f"CPU核心数: {self.cpu_count} (物理核心: {self.physical_cores})")
        logging.info(f"CPU使用率: {self.cpu_percent}%")
        logging.info(f"内存总量: {self.total_memory:.1f}GB")
        logging.info(f"内存使用率: {self.memory_percent}%")
        logging.info(f"建议线程数: {self.max_workers}")

    def setup_logging(self):
        """设置日志喵~"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"auto_extract_{time.strftime('%Y%m%d_%H%M%S')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def get_user_input(self):
        """获取用户输入喵~"""
        print("\n=== 测试模式配置 ===")
        self.old_xml_path = input("请输入旧版本XML文件路径: ").strip()
        self.new_xml_path = input("请输入新版本XML文件路径: ").strip()
        self.ffdec_path = input("请输入FFDec.jar完整路径: ").strip()
        
    def monitor_system_resources(self):
        """监控系统资源使用情况喵~"""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 90 or memory_percent > 90:
            logging.warning(f"系统资源使用率过高！CPU: {cpu_percent}%, 内存: {memory_percent}% 喵~")
            return False
        return True

    def process_version_xmls(self) -> Optional[str]:
        """处理用户提供的XML文件并生成差异文件喵~"""
        try:
            # 创建差异文件目录
            diff_dir = os.path.join(self.output_dir, "test_diff")
            os.makedirs(diff_dir, exist_ok=True)
            diff_xml = os.path.join(diff_dir, "diff.xml")

            # 加载XML文件
            old_root = load_xml(self.old_xml_path)
            new_root = load_xml(self.new_xml_path)
            if not old_root or not new_root:
                logging.error("XML文件加载失败喵~")
                return None

            # 比较XML并生成差异文件
            different_elements = compare_xml(old_root, new_root)
            if different_elements:
                write_new_xml(different_elements, diff_xml)
                logging.info(f"已生成测试差异文件: {diff_xml}")
                return diff_xml
            else:
                logging.info("未发现任何差异喵~")
                return None

        except Exception as e:
            logging.error(f"处理XML文件时出错: {str(e)} 喵~")
            return None

    def process_version(self) -> bool:
        """处理测试版本喵~"""
        try:
            # 生成差异XML文件
            diff_xml = self.process_version_xmls()
            if not diff_xml:
                return False

            # 2. 创建下载目录
            swf_dir = os.path.join(self.output_dir, "test_diff", "swf")
            os.makedirs(swf_dir, exist_ok=True)

            # 3. 根据差异文件下载SWF
            downloader = SwfDownloader(diff_xml, swf_dir)
            if not self.monitor_system_resources():
                self.max_workers = max(self.physical_cores, self.max_workers // 2)
                logging.info(f"由于系统负载高，调整线程数为: {self.max_workers} 喵~")
            successful, failed = downloader.download_all(max_workers=self.max_workers)
            logging.info(f"SWF下载完成 - 成功: {successful}, 失败: {failed} 喵~")

            if successful == 0:
                logging.error("没有成功下载任何SWF文件喵~")
                return False

            # 4. 使用FFDec导出
            if not os.path.exists(self.ffdec_path):
                logging.error(f"FFDec路径不存在: {self.ffdec_path} 喵~")
                return False
                
            exporter = FFDecExporter()
            exporter.ffdec_path = self.ffdec_path
            exporter.target_dir = swf_dir
            exporter.output_dir = os.path.join(self.output_dir, "test_diff", "exported")
            exporter.max_workers = self.max_workers
            if not self.monitor_system_resources():
                exporter.max_workers = max(self.physical_cores, self.max_workers // 2)
                logging.info(f"由于系统负载高，调整FFDec线程数为: {exporter.max_workers} 喵~")
            exporter.process_files()

            return True

        except Exception as e:
            logging.error(f"处理版本时出错: {str(e)} 喵~")
            return False

    def run(self):
        """运行测试模式喵~"""
        try:
            self.get_user_input()
            
            # 直接处理本地文件
            print("\n开始处理本地XML文件...")
            start_time = time.time()
            
            if self.process_version():
                print(f"\n测试处理完成!")
            else:
                print(f"\n测试处理失败!")

            print(f"总耗时: {time.time() - start_time:.2f}秒")

        except KeyboardInterrupt:
            print("\n程序已停止 喵~")
        except Exception as e:
            logging.error(f"程序执行出错: {str(e)} 喵~")

def main():
    extractor = AutoExtractor()
    extractor.run()

if __name__ == "__main__":
    main() 