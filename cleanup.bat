@echo off
chcp 65001 >nul
echo ========================================
echo 清理乱码文件
echo ========================================
echo.

echo 正在删除旧的乱码spec文件...
if exist "璇楄瘝绛旈宸ュ叿.spec" (
    del "璇楄瘝绛旈宸ュ叿.spec"
    echo 已删除旧的spec文件
) else (
    echo 旧的spec文件不存在
)

echo.
echo 正在清理build目录中的乱码文件夹...
if exist "build\璇楄瘝绛旈宸ュ叿" (
    rmdir /s /q "build\璇楄瘝绛旈宸ュ叿"
    echo 已删除build目录中的乱码文件夹
) else (
    echo build目录中的乱码文件夹不存在
)

echo.
echo 正在清理dist目录中的乱码exe文件...
if exist "dist\璇楄瘝绛旈宸ュ叿.exe" (
    del "dist\璇楄瘝绛旈宸ュ叿.exe"
    echo 已删除dist目录中的乱码exe文件
) else (
    echo dist目录中的乱码exe文件不存在
)

echo.
echo ========================================
echo 清理完成！
echo ========================================
echo.
echo 当前有效的文件：
echo - poetry_answer_tool.spec (打包配置文件)
echo - dist\PoetryAnswerTool.exe (可执行文件)
echo.
pause
