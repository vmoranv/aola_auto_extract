import os
import shutil

def find_and_copy_files(source_dir, target_dir, search_string):
    """
    查找source_dir及其子文件夹下所有包含search_string的文件，
    并将它们复制到target_dir中。
    
    :param source_dir: 要搜索的源文件夹路径
    :param target_dir: 目标文件夹路径，找到的文件将被复制到这里
    :param search_string: 用以匹配文件名的字符串
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if search_string in file:
                src_file_path = os.path.join(root, file)
                tgt_file_path = os.path.join(target_dir, file)
                
                # 如果目标文件夹中已经有同名文件，则跳过或可以选择覆盖
                if not os.path.exists(tgt_file_path):
                    shutil.copy2(src_file_path, tgt_file_path)  # copy2 保留元数据
                    print(f"Copied {src_file_path} to {tgt_file_path}")
                else:
                    print(f"File {tgt_file_path} already exists. Skipping.")

if __name__ == "__main__":
    # 用户需要提供源文件夹、目标文件夹以及搜索字符串
    source_directory = input("源文件夹: ")
    target_directory = input("目标文件夹: ")
    search_string = input("搜索字符串: ")

    find_and_copy_files(source_directory, target_directory, search_string)
