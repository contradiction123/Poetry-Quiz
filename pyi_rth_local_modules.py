"""
运行时hook：确保本地模块被正确加载
"""
import sys
import os

# 获取exe文件所在目录
if getattr(sys, 'frozen', False):
    # 如果是打包后的exe
    base_path = sys._MEIPASS
else:
    # 如果是开发环境
    base_path = os.path.dirname(os.path.abspath(__file__))

# 将当前目录添加到sys.path
if base_path not in sys.path:
    sys.path.insert(0, base_path)
