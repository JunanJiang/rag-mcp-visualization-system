@echo off
chcp 65001 >nul
echo ============================================================
echo   智能仿真报告生成系统 - JMeter 性能测试
echo   基于RAG和MCP技术的可视化场景设计与实现
echo ============================================================
echo.

:: 检查 JMeter 是否在 PATH 中
where jmeter >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 jmeter 命令，请检查：
    echo   1. 是否已安装 Apache JMeter
    echo   2. 是否已将 JMeter 的 bin 目录添加到系统 PATH
    echo   例如: set PATH=%%PATH%%;C:\apache-jmeter-5.6.3\bin
    echo.
    echo 下载地址: https://jmeter.apache.org/download_jmeter.cgi
    pause
    exit /b 1
)

:: 设置变量
set SCRIPT_DIR=%~dp0
set JMX_FILE=%SCRIPT_DIR%SimuReport_TestPlan.jmx
set RESULT_DIR=%SCRIPT_DIR%results
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set RESULT_CSV=%RESULT_DIR%\result_%TIMESTAMP%.csv
set REPORT_DIR=%RESULT_DIR%\html_report_%TIMESTAMP%

:: 创建结果目录
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo [1/3] 测试计划: %JMX_FILE%
echo [2/3] 结果文件: %RESULT_CSV%
echo [3/3] HTML报告: %REPORT_DIR%
echo.
echo 请确保后端服务已在 http://localhost:5000 运行!
echo.
pause

echo.
echo ▶ 正在执行 JMeter 测试 (非GUI模式)...
echo.

jmeter -n -t "%JMX_FILE%" -l "%RESULT_CSV%" -e -o "%REPORT_DIR%" -Jjmeter.save.saveservice.output_format=csv

echo.
if %errorlevel% equ 0 (
    echo ============================================================
    echo   ✅ 测试完成!
    echo ============================================================
    echo.
    echo   CSV结果:  %RESULT_CSV%
    echo   HTML报告: %REPORT_DIR%\index.html
    echo.
    echo   正在打开HTML报告...
    start "" "%REPORT_DIR%\index.html"
) else (
    echo ============================================================
    echo   ❌ 测试执行出错，请检查:
    echo   1. 后端服务是否在运行 (http://localhost:5000)
    echo   2. JMeter 安装是否正确
    echo ============================================================
)

echo.
pause
