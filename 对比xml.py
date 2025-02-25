import xml.etree.ElementTree as ET
import os

def load_xml(file_path):
    """加载XML文件并返回根元素"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件未找到: {file_path}")
    try:
        return ET.parse(file_path).getroot()
    except ET.ParseError as e:
        print(f"XML解析错误: {e}")
        return None

def compare_xml(old_root, new_root):
    """比较两个XML根元素，找出新XML中独有的n标签"""
    different_elements = []
    
    # 获取旧文件中所有n属性值的集合
    old_n_values = {elem.get('n') for elem in old_root.findall('.//f')}
    
    # 遍历新文件中的每个f标签
    for new_elem in new_root.findall('.//f'):
        n_attr = new_elem.get('n')
        
        # 如果这个n标签在旧文件中不存在
        if n_attr not in old_n_values:
            different_elements.append(new_elem)
            print(f"发现新标签: n=\"{n_attr}\"")
            print("-" * 50)
    
    return different_elements

def write_new_xml(different_elements, output_path):
    """将不同的元素写入新的XML文件"""
    # 创建根元素
    root = ET.Element('root')
    
    # 添加所有不同的元素
    for elem in different_elements:
        # 创建新的f标签
        new_f = ET.SubElement(root, 'f')
        # 复制n和v属性
        new_f.set('n', elem.get('n'))
        new_f.set('v', elem.get('v'))
    
    # 确保输出路径有.xml后缀
    if not output_path.endswith('.xml'):
        output_path += '.xml'
    
    # 创建ElementTree对象并写入文件
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

def main():
    try:
        old_file = input("请输入旧XML文件路径: ")
        new_file = input("请输入新XML文件路径: ")
        output_file = input("请输入输出XML文件路径: ")

        old_root = load_xml(old_file)
        new_root = load_xml(new_file)
        
        if old_root is None or new_root is None:
            print("XML文件加载失败")
            return
        
        different_elements = compare_xml(old_root, new_root)
        
        if different_elements:
            write_new_xml(different_elements, output_file)
            print(f"\n比较完成！发现 {len(different_elements)} 个新标签。")
            print(f"新标签已写入: {output_file}")
        else:
            print("未发现任何新标签。")
    
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
