# 奥拉星资源自动提取工具

## 项目介绍

这是一个用于自动监控、下载和提取奥拉星游戏资源的工具集合喵~。该工具可以检测游戏版本更新，并自动提取更新的资源文件，特别是对比新旧版本的XML文件，下载对应的SWF文件，并使用FFDec工具导出这些SWF文件中的资源。

## 主要功能

- 🔍 **版本监控**：自动监控奥拉星游戏版本更新
- 📊 **版本比较**：比较新旧版本的XML文件差异
- ⬇️ **资源下载**：根据差异文件自动下载更新的SWF资源文件
- 📦 **资源提取**：使用FFDec工具自动提取SWF文件中的资源
- 🔄 **系统优化**：根据系统资源自动调整线程数，避免系统负载过高
- 📝 **日志记录**：详细记录处理过程，便于排查问题

## 系统要求

- Python 3.7+
- Java（用于运行FFDec）
- [FFDec](https://github.com/jindrapetrik/jpexs-decompiler)（SWF反编译工具）

## 安装

1. 克隆仓库到本地：
```
git clone <repository-url>
```

2. 安装所需依赖：
```
pip install -r requirements.txt
```

3. 下载并安装FFDec工具：
   - 从[FFDec官网](https://github.com/jindrapetrik/jpexs-decompiler/releases)下载最新版本
   - 解压到任意目录

## 使用方法

### 自动模式（推荐）

运行自动提取程序：

```
python auto_extract_all.py
```

按照提示输入：
- FFDec.jar的路径
- 输出目录路径
- 线程数（建议使用默认值）

程序将自动监控版本更新，并在检测到更新时进行处理。

### 手动模式

如果需要手动处理特定的版本文件：

1. 提取版本XML：
```
python 自动提取版本xml.py
```

2. 比较XML差异：
```
python 对比xml.py
```

3. 下载对应SWF文件：
```
python 根据版本xml下载对应swf.py
```

4. 导出SWF文件资源：
```
python ffdec_export.py
```

## 文件结构

- `auto_extract_all.py` - 主程序，整合所有功能
- `自动提取版本xml.py` - 版本监控与XML提取
- `对比xml.py` - XML文件对比工具
- `根据版本xml下载对应swf.py` - SWF文件下载工具
- `ffdec_export.py` - FFDec导出工具
- `提取包含特定字符的文件到指定文件夹.py` - 文件筛选工具

## 日志

所有操作日志保存在`logs`目录下，便于排查问题。

## 输出

提取的资源文件保存在`output`目录下，结构如下：

```
output/
  └── diff_旧版本_新版本/
      ├── swf/         # 下载的SWF文件
      └── exported/    # 导出的资源文件
          ├── sprites/ # 导出的精灵动画
          └── scripts/ # 导出的脚本文件
```

## 注意事项

- 确保网络连接正常，以便正确获取版本信息和下载文件
- 根据系统性能调整线程数，避免系统负载过高
- FFDec版本建议使用22.0.0及以上版本 
