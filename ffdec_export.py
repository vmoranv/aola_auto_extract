#!/usr/bin/env python3
"""
使用 FFDec 导出指定文件夹及其子文件夹中的 SWF 文件的特定内容喵~
筛选条件：
  1. sprites 类：要求 SWF 文件中包含的 DefineSprite 标签中任一 Length 属性大于 200 的，
     则直接导出该 SWF 文件中所有 sprites 为 gif（或 avi）喵~
  2. scripts 文件：仅对文件名中包含 "config.as" 的 SWF 执行脚本提取操作，直接导出为 as 文件喵~
用户需输入 FFDec 工具（ffdec.jar）路径、目标 SWF 文件目录和输出基础目录，导出的文件将按类别分别存放喵~
"""

import os
import subprocess
import argparse
import logging
import re
import traceback
from datetime import datetime
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import time
import psutil
from tqdm import tqdm
import shutil

class FFDecExporter:
    def __init__(self):
        """初始化导出器喵~"""
        self.ffdec_path = ""
        self.target_dir = ""
        self.output_dir = ""
        # 获取CPU核心数，设置为物理核心数 * 2
        self.max_workers = psutil.cpu_count(logical=True)
        self.task_queue = Queue()
        self.results = []
        self.total_files = 0
        self.processed_files = 0
        self.setup_logging()
        self.pbar = None

    def setup_logging(self):
        """设置日志喵~"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"test_ffdec_{timestamp}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        logging.info(f"日志文件位置: {log_file} 喵~")

    def get_system_info(self):
        """获取系统信息喵~"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        print("\n=== 系统信息 ===")
        print(f"CPU使用率: {cpu_percent}%")
        print(f"CPU核心数: {psutil.cpu_count()} (物理核心: {psutil.cpu_count(logical=False)})")
        print(f"内存使用: {memory.percent}% (总计: {memory.total / (1024**3):.1f}GB)")
        print(f"磁盘使用: {disk.percent}% (总计: {disk.total / (1024**3):.1f}GB)")
        
        # 根据系统负载动态调整线程数
        if cpu_percent < 50:  # CPU负载较低，可以更激进
            self.max_workers = psutil.cpu_count(logical=True) * 2
        else:  # CPU负载较高，相对保守
            self.max_workers = psutil.cpu_count(logical=True)
        
        print(f"建议线程数: {self.max_workers} 喵~")

    def get_user_input(self):
        """获取用户输入喵~"""
        self.get_system_info()
        print("\n=== FFDec导出工具配置 ===")
        
        # 设置默认值
        default_ffdec = "D:/ffdec_22.0.1/ffdec.jar"
        default_target = "D:/game/MY/vscode/new/flashnew"
        default_output = "D:/game/MY/vscode/new/output"
        
        self.ffdec_path = input(f"请输入FFDec.jar的路径 (默认: {default_ffdec}): ").strip() or default_ffdec
        self.target_dir = input(f"请输入SWF文件目录路径 (默认: {default_target}): ").strip() or default_target
        self.output_dir = input(f"请输入输出目录路径 (默认: {default_output}): ").strip() or default_output
        
        try:
            user_threads = input(f"请输入线程数 (建议: {self.max_workers}, 回车使用建议值): ").strip()
            if user_threads:
                self.max_workers = int(user_threads)
        except ValueError:
            logging.warning(f"输入的线程数无效，使用建议值 {self.max_workers} 喵~")

    def validate_paths(self) -> bool:
        """验证路径是否有效喵~"""
        if not os.path.isfile(self.ffdec_path):
            logging.error(f"找不到FFDec工具：{self.ffdec_path} 喵~")
            return False
        if not os.path.exists(self.target_dir):
            logging.error(f"找不到目标SWF目录：{self.target_dir} 喵~")
            return False
        os.makedirs(self.output_dir, exist_ok=True)
        return True

    def count_total_files(self):
        """计算需要处理的总文件数喵~"""
        self.total_files = sum(1 for root, _, files in os.walk(self.target_dir)
                             for file in files if file.lower().endswith('.swf'))
        return self.total_files

    def update_progress(self):
        """更新进度条喵~"""
        if self.pbar:
            self.pbar.update(1)

    def process_file(self, swf_file: str) -> Tuple[bool, str]:
        """处理单个SWF文件喵~"""
        try:
            sprites_success = self.export_sprite(swf_file)
            scripts_success = self.export_script(swf_file)
            self.update_progress()
            return True, f"处理文件 {swf_file} 完成 喵~"
        except Exception as e:
            self.update_progress()
            return False, f"处理文件 {swf_file} 失败: {str(e)} 喵~"

    def process_files(self):
        """使用线程池处理所有文件喵~"""
        total_files = self.count_total_files()
        success_count = 0
        error_count = 0
        
        print(f"\n开始处理 {total_files} 个文件 喵~")
        
        with tqdm(total=total_files, desc="处理进度", unit="文件") as self.pbar:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for root, _, files in os.walk(self.target_dir):
                    for file in files:
                        if file.lower().endswith('.swf'):
                            swf_path = os.path.join(root, file)
                            futures.append(executor.submit(self.process_file, swf_path))

                for future in as_completed(futures):
                    try:
                        success, message = future.result()
                        if success:
                            success_count += 1
                            logging.info(message)
                        else:
                            error_count += 1
                            logging.error(message)
                    except Exception as e:
                        error_count += 1
                        logging.error(f"处理任务时发生错误: {str(e)} 喵~")

        print(f"\n处理完成！成功: {success_count}, 失败: {error_count} 喵~")

    def has_valid_sprite(self, swf_file_path: str) -> List[str]:
        """检查SWF文件中的sprite喵~"""
        cmd_dump = ["java", "-jar", self.ffdec_path, "-dumpSWF", swf_file_path]
        try:
            result = subprocess.run(cmd_dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                 text=True, check=True)
            valid_sprites = []
            for line in result.stdout.splitlines():
                if "DefineSprite" in line:
                    m = re.search(r"DefineSprite \(chid: (\d+)\).*?len=\s*(\d+)", line)
                    if m and int(m.group(2)) > 200:
                        valid_sprites.append(m.group(1))
            return valid_sprites
        except subprocess.CalledProcessError as e:
            logging.error(f"执行dump命令失败：{e} 喵~")
            return []

    def get_output_subdir(self, swf_path: str) -> str:
        """根据SWF路径生成输出子目录喵~"""
        # 获取相对于目标目录的相对路径
        rel_path = os.path.relpath(swf_path, self.target_dir)
        # 去除.swf扩展名并添加目录分隔符
        base_name = os.path.splitext(rel_path)[0]
        # 组合完整输出路径
        return os.path.join(self.output_dir, base_name)

    def export_sprite(self, swf_file_path: str) -> bool:
        """导出sprites喵~"""
        valid_sprites = self.has_valid_sprite(swf_file_path)
        if not valid_sprites:
            return True

        output_dir = os.path.join(self.get_output_subdir(swf_file_path), "sprites")
        os.makedirs(output_dir, exist_ok=True)

        success = True
        for sprite_id in valid_sprites:
            try:
                cmd_export = [
                    "java", "-jar", self.ffdec_path,
                    "-format", "sprite:gif",
                    "-selectid", sprite_id,
                    "-export", "sprite",
                    output_dir,  # 修改输出路径
                    swf_file_path
                ]
                subprocess.run(cmd_export, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"导出sprite {sprite_id}失败: {e} 喵~")
                success = False
        return success

    def export_script(self, swf_file_path: str) -> bool:
        """导出scripts喵~"""
        output_dir = os.path.join(self.get_output_subdir(swf_file_path), "scripts")
        os.makedirs(output_dir, exist_ok=True)

        try:
            cmd_dump = ["java", "-jar", self.ffdec_path, "-dumpAS3", swf_file_path]
            result = subprocess.run(cmd_dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                    text=True, check=True)
            config_scripts = [line.split()[0] for line in result.stdout.splitlines() 
                              if ".config." in line.lower()]
            
            success = True
            for class_name in config_scripts:
                cmd_export = [
                    "java", "-jar", self.ffdec_path,
                    "-format", "script:as",
                    "-selectclass", class_name,
                    "-export", "script",
                    output_dir,  # 保持原有导出方式喵~
                    swf_file_path
                ]
                try:
                    subprocess.run(cmd_export, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    success = False
                    logging.error(f"导出 {class_name} 失败: {e} 喵~")

            # 新增：提取导出的as文件到output_dir目录下，并删除空文件夹喵~
            for root, dirs, files in os.walk(output_dir, topdown=False):
                # 如果不是顶层scripts目录则处理喵~
                if os.path.abspath(root) != os.path.abspath(output_dir):
                    for file in files:
                        if file.lower().endswith('.as'):
                            src_path = os.path.join(root, file)
                            dst_path = os.path.join(output_dir, file)
                            if os.path.exists(dst_path):
                                # 如果目标文件已存在，则重命名以避免冲突喵~
                                base, ext = os.path.splitext(file)
                                counter = 1
                                new_name = f"{base}_{counter}{ext}"
                                dst_path = os.path.join(output_dir, new_name)
                                while os.path.exists(dst_path):
                                    counter += 1
                                    new_name = f"{base}_{counter}{ext}"
                                    dst_path = os.path.join(output_dir, new_name)
                            shutil.move(src_path, dst_path)
                            logging.info(f"移动 {src_path} 到 {dst_path} 喵~")
                    # 删除空目录喵~
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                            logging.info(f"删除空目录 {root} 喵~")
                    except Exception as e:
                        logging.error(f"删除目录 {root} 失败: {e} 喵~")
            
            # 若顶层scripts目录为空，则也删除之喵~
            if not os.listdir(output_dir):
                os.rmdir(output_dir)
                logging.info(f"删除空目录 {output_dir} 喵~")
            
            return success
        except subprocess.CalledProcessError as e:
            logging.error(f"导出scripts失败: {e} 喵~")
            return False

def main():
    """主函数喵~"""
    exporter = FFDecExporter()
    exporter.get_user_input()
    
    if not exporter.validate_paths():
        return
    
    start_time = time.time()
    exporter.process_files()
    end_time = time.time()
    
    print("\n=== 处理统计 ===")
    print(f"总耗时: {end_time - start_time:.2f}秒")
    print(f"平均每个文件耗时: {(end_time - start_time) / exporter.total_files:.2f}秒")
    print(f"使用线程数: {exporter.max_workers}")
    
    # 显示系统资源使用情况
    print("\n=== 系统资源使用 ===")
    print(f"CPU使用率: {psutil.cpu_percent()}%")
    print(f"内存使用率: {psutil.virtual_memory().percent}%")

if __name__ == "__main__":
    main()

# -----------------------------------------------
# 以下为测试模块（测试结束后请删除）喵~
def test_export_functions():
    """
    测试导出功能的简单测试函数喵~
    """
    test_ffdec_path = "D:/game/MY/vscode/ffdec_22.0.1/ffdec.jar"
    test_target_dir = "D:/game/MY/vscode/test_swf"
    test_output_dir = "D:/game/MY/vscode/test_output"
    process_swf_files(test_ffdec_path, test_target_dir, test_output_dir)
    print("测试结束，请检查输出目录，测试模块可删除喵~")

# 如果需要进行简单测试，可取消下面代码注释喵~
# test_export_functions()