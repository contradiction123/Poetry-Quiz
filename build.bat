@echo off
chcp 65001 >nul
echo ========================================
echo 开始打包程序...
echo ========================================
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 使用spec文件打包（避免中文文件名编码问题）
pyinstaller poetry_answer_tool.spec --clean

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo 可执行文件位置: dist\PoetryAnswerTool.exe
echo.
echo 注意：
echo 1. 首次运行exe时，OCR模型会自动下载（约100MB）
echo 2. 请确保config.json和exe在同一目录
echo 3. 数据库文件会在运行时自动创建
echo 4. 如需重命名为中文，请在打包后手动重命名
echo.
pause
