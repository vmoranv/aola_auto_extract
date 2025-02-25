import os
import requests
import xml.etree.ElementTree as ET
from tqdm import tqdm
import concurrent.futures
import time
from urllib.parse import urljoin

class SwfDownloader:
    def __init__(self, xml_path: str, save_dir: str):
        self.xml_path = xml_path
        self.save_dir = save_dir
        self.base_url = "http://aola.100bt.com/play/"
        self.failed_downloads = []
        self.retry_attempts = 3  # 重试次数
        self.retry_delay = 2     # 重试间隔(秒)
        self.swf_urls = self.parse_xml()
        
    def parse_xml(self) -> list:
        """解析XML文件获取所有SWF文件路径"""
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            urls = []
            
            for elem in root.findall('.//f'):
                if 'n' in elem.attrib:
                    swf_path = elem.attrib['n'] + '.swf'
                    full_url = urljoin(self.base_url, swf_path)
                    urls.append((full_url, swf_path))
                    
            return urls
        except Exception as e:
            print(f"解析XML文件出错: {str(e)}")
            return []
            
    def download_file(self, url_info: tuple, attempt: int = 1) -> bool:
        """下载单个SWF文件,支持重试"""
        url, relative_path = url_info
        save_path = os.path.join(self.save_dir, relative_path)
        
        # 如果文件已存在且大小大于0,跳过下载
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True
            
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                # 写入文件
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True
            elif response.status_code == 404:
                # 404错误不重试
                self.failed_downloads.append((url, f"HTTP 404"))
                return False
            else:
                # 其他错误考虑重试
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay)
                    return self.download_file(url_info, attempt + 1)
                else:
                    self.failed_downloads.append((url, f"HTTP {response.status_code} after {attempt} attempts"))
                    return False
        except Exception as e:
            # 网络错误等也考虑重试
            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay)
                return self.download_file(url_info, attempt + 1)
            else:
                self.failed_downloads.append((url, f"{str(e)} after {attempt} attempts"))
                return False

    def retry_failed_downloads(self):
        """重试下载失败的文件"""
        if not self.failed_downloads:
            return 0, 0
            
        print("\n开始重试下载失败的文件...")
        retry_urls = []
        
        # 筛选出非404错误的URL
        for url, error in self.failed_downloads:
            if "HTTP 404" not in error:
                relative_path = url.replace(self.base_url, '')
                retry_urls.append((url, relative_path))
        
        if not retry_urls:
            print("没有需要重试的文件")
            return 0, 0
            
        # 清空之前的失败记录
        self.failed_downloads = []
        
        # 重试下载
        successful = 0
        failed = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.download_file, url_info): url_info 
                      for url_info in retry_urls}
            
            with tqdm(total=len(retry_urls), desc="重试进度") as pbar:
                for future in concurrent.futures.as_completed(futures):
                    try:
                        if future.result():
                            successful += 1
                        else:
                            failed += 1
                    except Exception as e:
                        failed += 1
                    pbar.update(1)
                    
        return successful, failed

    def download_all(self, max_workers: int = 5):
        """批量下载所有SWF文件"""
        if not self.swf_urls:
            print("没有找到需要下载的文件")
            return 0, 0
            
        total_files = len(self.swf_urls)
        successful = 0
        failed = 0
        
        print(f"找到 {total_files} 个SWF文件需要下载")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.download_file, url_info): url_info 
                      for url_info in self.swf_urls}
            
            with tqdm(total=total_files, desc="下载进度") as pbar:
                for future in concurrent.futures.as_completed(futures):
                    url_info = futures[future]
                    try:
                        if future.result():
                            successful += 1
                        else:
                            failed += 1
                    except Exception as e:
                        failed += 1
                        self.failed_downloads.append((url_info[0], str(e)))
                    pbar.update(1)
        
        # 重试失败的下载
        if self.failed_downloads:
            retry_successful, retry_failed = self.retry_failed_downloads()
            successful += retry_successful
            failed = retry_failed  # 更新最终的失败数
            
        return successful, failed

    def save_error_log(self):
        """保存错误日志"""
        if self.failed_downloads:
            log_path = os.path.join(self.save_dir, 'download_errors.log')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("下载失败的文件:\n")
                for url, error in self.failed_downloads:
                    f.write(f"{url}: {error}\n")

def main():
    try:
        # 获取用户输入
        xml_path = input("请输入XML文件路径: ").strip()
        save_dir = input("请输入保存文件夹路径: ").strip()
        workers = int(input("请输入同时下载的数量（建议5-10）: ").strip())
        
        # 创建下载器实例
        downloader = SwfDownloader(xml_path, save_dir)
        
        # 开始计时
        start_time = time.time()
        
        # 开始下载
        successful, failed = downloader.download_all(max_workers=workers)
        
        # 输出结果
        print(f"\n下载完成!")
        print(f"成功: {successful}")
        print(f"失败: {failed}")
        print(f"总耗时: {time.time() - start_time:.2f}秒")
        
        # 保存错误日志
        downloader.save_error_log()
        
    except KeyboardInterrupt:
        print("\n用户中断下载")
        downloader.save_error_log()
    except Exception as e:
        print(f"程序执行出错: {str(e)}")

if __name__ == "__main__":
    main()
