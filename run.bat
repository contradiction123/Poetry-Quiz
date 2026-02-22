@echo off
chcp 65001 >nul
title 诗词答题自动化工具
cd /d "%~dp0"

:: 禁用 PaddlePaddle PIR API 和 oneDNN，解决兼容性问题
set FLAGS_enable_pir_api=0
set FLAGS_use_mkldnn=0
set FLAGS_enable_pir_in_executor=0

echo 正在启动诗词答题自动化工具...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo 程序运行出错，请检查 Python 环境和依赖是否安装正确。
    echo 可尝试运行: pip install -r requirements.txt
    pause
)
