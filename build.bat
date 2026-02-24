@echo off
chcp 65001 >nul
echo ========================================
echo 开始打包程序...
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo 错误：未找到虚拟环境！
    echo 请先创建虚拟环境并安装依赖：
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查PyInstaller是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller>=5.13.0
)

REM 清理之前的打包文件
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo.
echo 开始打包，请稍候...
echo 注意：首次打包可能需要较长时间（5-10分钟）
echo.

REM 使用spec文件打包（避免中文文件名编码问题）
pyinstaller poetry_answer_tool.spec --clean

if errorlevel 1 (
    echo.
    echo ========================================
    echo 打包失败！
    echo ========================================
    echo 请检查错误信息并重试
    pause
    exit /b 1
)

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo 可执行文件位置: dist\PoetryAnswerTool.exe
echo.
echo 分发说明：
echo 1. 将 dist 目录下的 PoetryAnswerTool.exe 复制给其他用户
echo 2. 同时提供 config.example.json 文件（用户需要重命名为 config.json 并配置API Key）
echo 3. 首次运行exe时，OCR模型会自动下载（约100MB），需要网络连接
echo 4. 数据库文件会在运行时自动创建
echo 5. 如需重命名为中文，请在打包后手动重命名
echo.
echo 打包文件大小检查：
dir dist\PoetryAnswerTool.exe
echo.
pause
