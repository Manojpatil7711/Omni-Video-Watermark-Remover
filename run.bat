@echo off
setlocal
cd /d "%~dp0"

echo === 1/3 Checking Python ===
python --version >nul 2>&1 || (echo ERROR: Python is not installed or not on PATH.& exit /b 1)

echo === 2/3 Creating virtual environment ===
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .

set "INPUT_VIDEO=%~1"
if "%INPUT_VIDEO%"=="" set "INPUT_VIDEO=input.mp4"
set "OUTPUT_VIDEO=%~2"
if "%OUTPUT_VIDEO%"=="" set "OUTPUT_VIDEO=clean_output.mp4"
set "MODE=%~3"
if "%MODE%"=="" set "MODE=static"
set "ENGINE=%~4"
if "%ENGINE%"=="" set "ENGINE=fast"

if not exist "%INPUT_VIDEO%" (
  echo ERROR: Input video not found: %INPUT_VIDEO%
  exit /b 2
)

echo === 3/3 Processing video ===
python -m omni_watermark.cli --input "%INPUT_VIDEO%" --output "%OUTPUT_VIDEO%" --mode "%MODE%" --engine "%ENGINE%"
if errorlevel 1 exit /b %errorlevel%

echo.
echo ========================================
echo Processing completed successfully!
echo Output: %OUTPUT_VIDEO%
echo ========================================
pause
