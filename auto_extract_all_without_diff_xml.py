import os
import time
import logging
from typing import List, Dict
import psutil
from tqdm import tqdm
import re
from datetime import datetime
import tempfile
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import xml.etree.ElementTree as ET

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
        # 添加日期过滤变量
        self.start_date = ""
        self.end_date = ""
        # 添加版本监视器
        self.version_monitor = VersionMonitor()

    @staticmethod
    def parse_version_date(version_str):
        """从版本字符串中提取日期（前8位）"""
        if len(version_str) >= 8:
            date_part = version_str[:8]
            try:
                return datetime.strptime(date_part, '%Y%m%d')
            except ValueError:
                return None
        return None

    @staticmethod
    def filter_xml_by_date_range(xml_root, start_date_str, end_date_str):
        """根据日期范围过滤XML条目"""
        try:
            start_date = datetime.strptime(start_date_str, '%Y%m%d') if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y%m%d') if end_date_str else None
        except ValueError as e:
            logging.error(f"日期格式错误: {e}")
            return None
        
        filtered_elements = []
        
        for element in xml_root.findall('.//f'):
            version = element.get('v', '')
            element_date = AutoExtractor.parse_version_date(version)
            if element_date:
                # 检查是否在指定日期范围内
                if start_date and element_date < start_date:
                    continue
                if end_date and element_date > end_date:
                    continue
                filtered_elements.append(element)
            elif not start_date and not end_date:
                # 如果没有指定日期范围，包含所有元素
                filtered_elements.append(element)
        
        return filtered_elements

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
        # 先获取FFDec路径，因为无论哪种模式都需要
        self.ffdec_path = input("请输入FFDec.jar完整路径: ").strip()
        
        print("\n=== 模式选择 ===")
        mode = input("请选择模式 (1: 自动模式, 2: 手动选择XML文件): ").strip()
        
        # 添加时间段过滤选项（无论哪种模式都需要）
        print("\n=== 时间段过滤设置（可选）===")
        print("时间格式: YYYYMMDD (如: 20250101)")
        print("留空表示不限制该端点")
        self.start_date = input("请输入开始日期 (留空表示不限制): ").strip()
        self.end_date = input("请输入结束日期 (留空表示不限制): ").strip()
        
        if self.start_date or self.end_date:
            print(f"已设置时间过滤: {self.start_date or '不限制'} 到 {self.end_date or '不限制'}")
        
        if mode == "1":
            # 自动模式 - 获取最新版本XML并直接处理
            return self.auto_process_version()
        elif mode == "2":
            # 手动模式 - 用户选择两个XML文件进行对比
            print("\n=== 手动选择模式 ===")
            self.old_xml_path = input("请输入旧版本XML文件路径: ").strip()
            self.new_xml_path = input("请输入新版本XML文件路径: ").strip()
            return True
        else:
            print("无效的选择，默认使用自动模式")
            return self.auto_process_version()

    def auto_process_version(self):
        """自动获取最新版本XML并处理时间段 喵~"""
        print("\n=== 自动处理版本XML ===")
        # 创建版本文件目录（如果不存在）
        version_dir = os.path.join(self.base_dir, "version_files")
        os.makedirs(version_dir, exist_ok=True)
        
        # 获取最新的XML版本
        try:
            # 设置FFdec路径
            self.version_monitor.ffdec_path = self.ffdec_path
            current_version = self.version_monitor.get_version()
            
            if not current_version:
                logging.error("无法获取版本号喵~")
                return False
            
            logging.info(f"获取到当前版本号: {current_version}")
            
            # 下载并解包当前版本
            version_dir_current = os.path.join(self.base_dir, "version_current")
            if not self.version_monitor.download_and_extract(current_version, False):
                logging.error("下载或解包版本失败喵~")
                return False
            
            # 找到最新的XML文件
            binary_dir = os.path.join(version_dir_current, "binary")
            latest_xml = None
            latest_date = None
            
            for root, _, files in os.walk(binary_dir):
                for file in files:
                    if file.endswith('.xml'):
                        src_file = os.path.join(root, file)
                        if latest_xml is None or os.path.getmtime(src_file) > latest_date:
                            latest_xml = src_file
                            latest_date = os.path.getmtime(src_file)
            
            if not latest_xml:
                logging.error("找不到XML文件喵~")
                return False
            
            logging.info(f"找到最新XML文件: {latest_xml}")
            
            # 使用最新的XML作为新版本XML，不需要旧版本XML进行对比
            self.new_xml_path = latest_xml
            
            # 直接处理最新XML中的时间区间，不需要旧版本进行对比
            # 这里引入一个空的旧版本XML（可以是一个空文件或者相同文件的副本）
            empty_xml = os.path.join(self.output_dir, "empty.xml")
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 创建一个空的XML作为比较基准
            with open(empty_xml, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n<root>\n</root>')
            
            self.old_xml_path = empty_xml
            logging.info(f"已设置 - 新版本XML: {self.new_xml_path}, 旧版本XML: 空XML文件")
            
            return True
            
        except Exception as e:
            logging.error(f"自动处理版本XML失败: {str(e)} 喵~")
            return False

    def extract_date_from_filename(self, filename):
        """从文件名中提取日期 喵~"""
        match = re.search(r'(\d{8})\.xml', filename)
        if match:
            return match.group(1)
        return "未知日期"

    def normalize_version_date(self, version_str):
        """标准化版本日期格式 喵~"""
        if not version_str:
            return None
        
        # 处理长格式时间戳 (如 2016022597279620)
        if len(version_str) > 8 and version_str.startswith('20'):
            return version_str[:8]
        
        # 处理短格式时间戳 (如 140929)
        if len(version_str) == 6 and version_str[0] in ('1', '2'):
            return '20' + version_str
        
        # 其他格式保持原样
        return version_str

    def is_version_in_timerange(self, version):
        """检查版本是否在指定的时间范围内喵~"""
        if not version:
            return True  # 如果没有版本号，默认包含
        
        # 尝试从版本号中提取日期部分
        normalized_date = None
        
        # 处理不同格式的版本号
        if len(version) >= 8 and version.startswith(('20', '19')):
            # 格式1: 2025061943687406 - 取前8位作为日期 (YYYYMMDD)
            normalized_date = version[:8]
        elif len(version) >= 6 and version[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
            # 格式2: 250612214398701 - 取前6位，并添加 "20" 前缀
            year_prefix = "20" if version[:2] < "50" else "19"
            normalized_date = year_prefix + version[:6]
        elif len(version) <= 4:
            return False
        
        logging.debug(f"版本号 {version} 解析为日期: {normalized_date}")
        
        if not normalized_date or len(normalized_date) != 8:
            return False
        
        if self.start_date and normalized_date < self.start_date:
            return False
        
        if self.end_date and normalized_date > self.end_date:
            return False
        
        return True

    def monitor_system_resources(self):
        """监控系统资源使用情况喵~"""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 90 or memory_percent > 90:
            logging.warning(f"系统资源使用率过高！CPU: {cpu_percent}%, 内存: {memory_percent}% 喵~")
            return False
        return True

    def process_version(self):
        """处理版本XML和下载对应SWF喵~"""
        try:
            if self.old_xml_path == os.path.join(self.output_dir, "empty.xml"):
                # 自动模式：直接处理新XML文件中符合时间范围的内容
                return self.process_single_xml(self.new_xml_path)
            else:
                # 手动模式：对比两个XML文件
                return self.process_compare_xml()
        except Exception as e:
            logging.error(f"处理版本时出错: {str(e)} 喵~")
            return False

    def get_thread_count(self):
        """获取最佳线程数喵~"""
        return self.max_workers

    def process_single_xml(self, xml_path):
        """处理单个XML文件喵~"""
        try:
            logging.info(f"加载XML文件: {xml_path}")
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            logging.info("开始提取符合时间范围的条目...")
            
            # 统计不同版本号格式的数量
            format1_count = 0  # 2025061943687406
            format2_count = 0  # 250612214398701
            format3_count = 0  # 1210
            unknown_count = 0  # 其他格式
            
            # 筛选符合时间范围的条目
            filtered_elements = []
            for elem in root.findall(".//f"):
                version = elem.get("v", "")
                
                # 统计版本号格式
                if len(version) >= 8 and version.startswith(('20', '19')):
                    format1_count += 1
                elif len(version) >= 6 and version[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
                    format2_count += 1
                elif len(version) <= 4:
                    format3_count += 1
                else:
                    unknown_count += 1
                
                if self.is_version_in_timerange(version):
                    filtered_elements.append(elem)
            
            logging.info(f"找到 {len(filtered_elements)} 个符合条件的条目喵~")
            logging.info(f"版本号格式统计: 长格式: {format1_count}, 短格式: {format2_count}, 超短格式: {format3_count}, 未知格式: {unknown_count}")
            
            # 创建新的XML树
            new_root = ET.Element("versiondata")
            valid_elements_count = 0
            
            for elem in filtered_elements:
                # 检查元素是否有必要的属性
                if 'n' in elem.attrib and 'v' in elem.attrib:
                    path = elem.get('n')
                    version = elem.get('v')
                    
                    # 创建新元素并添加到新树
                    new_elem = ET.SubElement(new_root, "f")
                    new_elem.set("n", path)
                    new_elem.set("v", version)
                    valid_elements_count += 1
                else:
                    logging.warning(f"跳过缺少必要属性的元素: {ET.tostring(elem, encoding='unicode').strip()}")
            
            logging.info(f"创建了新的XML树，包含 {valid_elements_count} 个元素")
            
            # 保存结果XML
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_xml_path = os.path.join(self.output_dir, f"result_{timestamp}.xml")
            
            # 创建输出目录（如果不存在）
            os.makedirs(os.path.dirname(result_xml_path), exist_ok=True)
            
            # 保存XML文件
            tree = ET.ElementTree(new_root)
            tree.write(result_xml_path, encoding="utf-8", xml_declaration=True)
            logging.info(f"已保存结果XML到文件: {result_xml_path}")
            
            # 下载SWF文件
            swf_dir = os.path.join(self.output_dir, "swf_files", timestamp)
            os.makedirs(swf_dir, exist_ok=True)
            
            logging.info(f"开始从XML下载SWF文件: {result_xml_path}")
            
            # 直接使用我们自己的下载方法
            self.download_swf_files(result_xml_path, swf_dir)
            
            # 检查是否有下载的SWF文件
            swf_files = []
            for root, dirs, files in os.walk(swf_dir):
                for file in files:
                    if file.lower().endswith('.swf'):
                        swf_files.append(os.path.join(root, file))
            
            if swf_files:
                logging.info(f"找到 {len(swf_files)} 个已下载的SWF文件")
                # 处理下载的SWF文件
                self.process_swf_files(swf_dir)
            else:
                logging.warning("没有找到已下载的SWF文件，跳过处理步骤")
            
            return True
        except Exception as e:
            logging.error(f"处理XML文件失败: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def download_swf_files(self, xml_path, output_dir):
        """从XML文件下载SWF文件"""
        try:
            # 解析XML文件
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # 收集需要下载的文件
            files_to_download = []
            for elem in root.findall(".//f"):
                if 'n' in elem.attrib and 'v' in elem.attrib:
                    path = elem.get('n')
                    version = elem.get('v')
                    
                    # 构建URL和本地路径
                    url = f"https://aola.100bt.com/play/{path}.swf"
                    local_dir = os.path.join(output_dir, os.path.dirname(path))
                    local_path = os.path.join(output_dir, f"{path}.swf")
                    
                    # 创建目录
                    os.makedirs(local_dir, exist_ok=True)
                    
                    files_to_download.append((url, local_path, version))
            
            if not files_to_download:
                logging.warning("没有找到需要下载的文件")
                return
            
            logging.info(f"找到 {len(files_to_download)} 个文件需要下载")
            
            # 使用线程池下载文件
            successful = 0
            failed = 0
            
            with tqdm(total=len(files_to_download), desc="下载进度") as pbar:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_url = {
                        executor.submit(self._download_file, url, local_path): (url, local_path, version)
                        for url, local_path, version in files_to_download
                    }
                    
                    for future in as_completed(future_to_url):
                        url, local_path, version = future_to_url[future]
                        try:
                            result = future.result()
                            if result:
                                successful += 1
                            else:
                                failed += 1
                        except Exception as e:
                            logging.error(f"下载文件时出错: {url} -> {str(e)}")
                            failed += 1
                        finally:
                            pbar.update(1)
            
            logging.info(f"SWF文件下载完成! 成功: {successful}, 失败: {failed}")
            
        except Exception as e:
            logging.error(f"下载SWF文件时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())

    def _download_file(self, url, local_path):
        """下载单个文件"""
        try:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 下载文件
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
        except Exception as e:
            logging.error(f"下载文件失败: {url} -> {str(e)}")
            return False

    def process_compare_xml(self):
        """对比两个XML文件喵~（手动模式）"""
        try:
            # 加载XML文件
            old_data = load_xml(self.old_xml_path)
            new_data = load_xml(self.new_xml_path)
            
            # 使用is not None代替布尔检查
            if old_data is None or new_data is None:
                logging.error("XML加载失败喵~")
                return False
            
            logging.info("XML加载成功，开始对比...")
            
            # 对比XML文件
            added_items, modified_items = compare_xml(old_data, new_data)
            
            # 应用时间段过滤
            if self.start_date or self.end_date:
                logging.info(f"应用时间过滤: {self.start_date or '不限'} 到 {self.end_date or '不限'}")
                
                filtered_added = []
                for item in added_items:
                    if self.is_version_in_timerange(item.get('v')):
                        filtered_added.append(item)
                        
                filtered_modified = []
                for old_item, new_item in modified_items:
                    if self.is_version_in_timerange(new_item.get('v')):
                        filtered_modified.append((old_item, new_item))
                        
                logging.info(f"过滤前: {len(added_items)} 个新增项, {len(modified_items)} 个修改项")
                logging.info(f"过滤后: {len(filtered_added)} 个新增项, {len(filtered_modified)} 个修改项")
                
                added_items = filtered_added
                modified_items = filtered_modified
            
            # 创建输出目录
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 生成新的XML文件
            result_xml_path = os.path.join(self.output_dir, "result.xml")
            write_new_xml(added_items, modified_items, result_xml_path)
            
            # 创建SWF下载目录 - 使用临时目录避免权限问题
            # 创建唯一的临时目录路径
            temp_base = os.path.join(tempfile.gettempdir(), "swf_downloader_" + str(int(time.time())))
            swf_dir = os.path.join(temp_base, "swf")
            
            # 确保目录不存在，然后创建它
            if os.path.exists(swf_dir):
                try:
                    shutil.rmtree(swf_dir)  # 递归删除目录及其内容
                except Exception as e:
                    logging.warning(f"无法删除已存在的目录: {e}")
                    # 使用备用名称
                    swf_dir = os.path.join(temp_base + "_alt", "swf")
            
            try:
                os.makedirs(swf_dir, exist_ok=True)
                # 确保目录存在且可写
                test_file = os.path.join(swf_dir, "test.txt")
                with open(test_file, 'w') as f:
                    f.write("测试写入权限")
                os.remove(test_file)  # 删除测试文件
                logging.info(f"成功创建临时下载目录: {swf_dir}")
            except Exception as e:
                logging.error(f"无法创建或写入下载目录: {e}")
                # 最后尝试使用用户主目录
                swf_dir = os.path.join(os.path.expanduser("~"), "swf_download_" + str(int(time.time())))
                os.makedirs(swf_dir, exist_ok=True)
                logging.info(f"使用备用下载目录: {swf_dir}")
            
            try:
                # 下载SWF文件
                # 最终修复：根据错误信息推断，构造函数用于配置，download_all用于执行
                swf_downloader = SwfDownloader(swf_dir, self.get_thread_count())
                swf_files = swf_downloader.download_all(result_xml_path)
                
                if not swf_files:
                    logging.warning("没有SWF文件需要下载喵~")
                    return True
                    
                # 创建FFDecExporter并设置属性
                exporter = FFDecExporter()
                exporter.ffdec_path = self.ffdec_path
                exporter.target_dir = swf_dir  # 设置下载好的SWF所在目录
                exporter.output_dir = os.path.join(self.output_dir, "ffdec_output")  # 设置输出目录
                exporter.max_workers = self.max_workers  # 设置线程数
                
                # 调用process_files方法处理所有文件
                logging.info("开始处理SWF文件...")
                exporter.process_files()
                
                logging.info("SWF文件处理完成 喵~")
                return True
            
            except Exception as e:
                logging.error(f"SWF处理出错: {str(e)}")
                # 即使SWF处理失败，也返回True，因为XML处理已经成功
                return True
            
        except Exception as e:
            logging.error(f"对比XML文件时出错: {str(e)} 喵~")
            return False

    def process_swf_files(self, swf_dir):
        """处理下载的SWF文件喵~"""
        logging.info(f"开始处理下载的SWF文件...")
        
        # 检查目录是否存在
        if not os.path.exists(swf_dir) or not os.path.isdir(swf_dir):
            logging.error(f"SWF目录不存在或不是一个目录: {swf_dir}")
            return False
        
        # 检查是否有SWF文件
        swf_files = []
        for root, _, files in os.walk(swf_dir):
            for file in files:
                if file.lower().endswith('.swf'):
                    swf_files.append(os.path.join(root, file))
        
        if not swf_files:
            logging.warning("没有找到SWF文件进行处理喵~")
            return True
        
        logging.info(f"找到 {len(swf_files)} 个SWF文件需要处理")
        
        # 创建导出目录 - 也放在output文件夹下
        export_dir = os.path.join(self.output_dir, "extracted_swf")
        os.makedirs(export_dir, exist_ok=True)
        
        # 创建FFDec导出器
        exporter = FFDecExporter()
        
        # 设置FFDec路径
        exporter.ffdec_path = self.ffdec_path
        
        # 设置目标目录和输出目录
        exporter.target_dir = swf_dir
        exporter.output_dir = export_dir
        
        # 使用我们的线程数设置
        exporter.max_workers = self.max_workers
        
        # 处理文件
        exporter.process_files()
        
        logging.info(f"SWF文件处理完成! 文件已导出到: {export_dir}")
        
        return True

    def run(self):
        """运行程序喵~"""
        try:
            if not self.get_user_input():
                logging.error("获取用户输入失败喵~")
                return
            
            if not self.old_xml_path or not self.new_xml_path:
                logging.error("未提供有效的XML文件路径喵~")
                return
            
            print("\n开始处理XML文件...")
            start_time = time.time()
            
            if self.process_version():
                print("\n处理完成!")
            else:
                print("\n处理失败!")

            print(f"总耗时: {time.time() - start_time:.2f}秒")

        except KeyboardInterrupt:
            print("\n程序已停止 喵~")
        except Exception as e:
            logging.error(f"程序执行出错: {str(e)} 喵~")

class SwfDownloader:
    """下载SWF文件的类喵~"""
    
    def __init__(self, xml_path, output_dir):
        """初始化下载器喵~"""
        self.xml_path = xml_path
        self.output_dir = output_dir
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "http://res.mmo.qq.com/swf/"
        self.failed_files = []
    
    def download_all(self, max_workers=8):
        """下载XML中所有的SWF文件喵~
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            下载的SWF文件列表
        """
        try:
            # 解析XML文件
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            
            # 提取所有需要下载的文件
            files_to_download = []
            for item in root.findall('.//f'):
                url = item.get('u', '')
                if url and url.endswith('.swf'):
                    files_to_download.append(url)
            
            if not files_to_download:
                print("没有找到需要下载的文件")
                return []
            
            # 下载文件
            downloaded_files = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for url in files_to_download:
                    future = executor.submit(self.download_file, url)
                    futures.append(future)
                
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        downloaded_files.append(result)
            
            return downloaded_files
            
        except Exception as e:
            print(f"解析XML文件出错: {str(e)}")
            return []
    
    def download_file(self, url):
        """下载单个SWF文件喵~
        
        Args:
            url: SWF文件URL
            
        Returns:
            下载的文件路径，如果下载失败则返回None
        """
        try:
            # 提取文件名
            filename = os.path.basename(url)
            output_path = os.path.join(self.output_dir, filename)
            
            # 下载文件
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return output_path
            
        except Exception as e:
            logging.error(f"下载文件 {url} 失败: {str(e)}")
            return None

def main():
    extractor = AutoExtractor()
    extractor.run()

if __name__ == "__main__":
    main() 