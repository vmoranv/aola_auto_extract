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
        print("\n=== 系统信息 ===")
        print(f"CPU核心数: {self.cpu_count} (物理核心: {self.physical_cores})")
        print(f"CPU使用率: {self.cpu_percent}%")
        print(f"内存总量: {self.total_memory:.1f}GB")
        print(f"内存使用率: {self.memory_percent}%")
        print(f"建议线程数: {self.max_workers}")
        
        print("\n=== 自动提取配置 ===")
        # 设置默认值
        default_ffdec = "D:/ffdec_22.0.1/ffdec.jar"
        self.ffdec_path = input(f"请输入FFDec.jar的路径 (默认: {default_ffdec}): ").strip() or default_ffdec
        self.output_dir = input(f"请输入输出目录路径 (默认: {self.output_dir}): ").strip() or self.output_dir
        
        try:
            user_threads = input(f"请输入线程数 (建议: {self.max_workers}, 回车使用建议值): ").strip()
            if user_threads:
                user_threads = int(user_threads)
                if user_threads > self.max_workers * 1.5:  # 如果用户输入的线程数过高
                    logging.warning(f"警告：设置的线程数 {user_threads} 可能会导致系统负载过高喵~")
                    if input("是否继续使用该线程数？(y/n): ").lower() != 'y':
                        user_threads = self.max_workers
                self.max_workers = user_threads
        except ValueError:
            logging.warning(f"输入的线程数无效，使用建议值 {self.max_workers} 喵~")

    def monitor_system_resources(self):
        """监控系统资源使用情况喵~"""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 90 or memory_percent > 90:
            logging.warning(f"系统资源使用率过高！CPU: {cpu_percent}%, 内存: {memory_percent}% 喵~")
            return False
        return True

    def process_version_xmls(self, current_version: str, new_version: str) -> Optional[str]:
        """处理版本XML文件并生成差异文件喵~"""
        try:
            # 获取当前版本和新版本的XML文件路径
            current_xml = self.find_latest_xml(os.path.join(self.base_dir, "version_current", "binary"))
            new_xml = self.find_latest_xml(os.path.join(self.base_dir, "version_new", "binary"))
            
            if not current_xml or not new_xml:
                logging.error("未找到XML文件喵~")
                return None

            # 创建差异文件目录
            diff_dir = os.path.join(self.output_dir, f"diff_{current_version}_{new_version}")
            os.makedirs(diff_dir, exist_ok=True)
            diff_xml = os.path.join(diff_dir, "diff.xml")

            # 加载XML文件
            old_root = load_xml(current_xml)
            new_root = load_xml(new_xml)
            if not old_root or not new_root:
                logging.error("XML文件加载失败喵~")
                return None

            # 比较XML并生成差异文件
            different_elements = compare_xml(old_root, new_root)
            if different_elements:
                write_new_xml(different_elements, diff_xml)
                logging.info(f"已生成差异文件: {diff_xml}")
                return diff_xml
            else:
                logging.info("未发现任何差异喵~")
                return None

        except Exception as e:
            logging.error(f"处理XML文件时出错: {str(e)} 喵~")
            return None

    def find_latest_xml(self, directory: str) -> Optional[str]:
        """查找目录中最新的XML文件喵~"""
        try:
            if not os.path.exists(directory):
                return None
            xml_files = [f for f in os.listdir(directory) if f.endswith('.xml')]
            if not xml_files:
                return None
            latest_xml = max(xml_files, key=lambda x: os.path.getctime(os.path.join(directory, x)))
            return os.path.join(directory, latest_xml)
        except Exception as e:
            logging.error(f"查找XML文件时出错: {str(e)} 喵~")
            return None

    def process_version(self, current_version: str, new_version: str) -> bool:
        """处理版本更新喵~"""
        try:
            # 1. 生成差异XML文件
            diff_xml = self.process_version_xmls(current_version, new_version)
            if not diff_xml:
                return False

            # 2. 创建下载目录
            swf_dir = os.path.join(self.output_dir, f"diff_{current_version}_{new_version}", "swf")
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
            exporter = FFDecExporter()
            exporter.ffdec_path = self.ffdec_path
            exporter.target_dir = swf_dir
            exporter.output_dir = os.path.join(self.output_dir, f"diff_{current_version}_{new_version}", "exported")
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
        """运行自动提取喵~"""
        try:
            self.get_user_input()
            
            # 创建版本监控器
            monitor = VersionMonitor()
            
            while True:
                print("\n等待版本更新...")
                current_version, new_version = monitor.run(self.ffdec_path)
                
                if current_version and new_version:
                    print(f"\n检测到版本更新: {current_version} -> {new_version}")
                    start_time = time.time()
                    
                    if self.process_version(current_version, new_version):
                        print(f"\n版本差异处理完成!")
                    else:
                        print(f"\n版本差异处理失败!")

                    print(f"总耗时: {time.time() - start_time:.2f}秒")
                    
                    # 询问是否继续监控
                    if input("\n是否继续监控版本更新? (y/n): ").lower() != 'y':
                        break
                else:
                    print("获取版本信息失败，请检查网络连接喵~")
                    if input("\n是否重试? (y/n): ").lower() != 'y':
                        break

        except KeyboardInterrupt:
            print("\n程序已停止 喵~")
        except Exception as e:
            logging.error(f"程序执行出错: {str(e)} 喵~")

def main():
    extractor = AutoExtractor()
    extractor.run()

if __name__ == "__main__":
    main() 