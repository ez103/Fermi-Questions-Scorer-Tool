@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Complete the standard app setup in README.md first.
  pause
  exit /b 1
)
if not exist .venv-paddle\Scripts\python.exe (
  .venv\Scripts\python.exe -m venv .venv-paddle
  if errorlevel 1 goto failed
)
.venv-paddle\Scripts\python.exe -m pip install -r requirements-paddle.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe download_paddle_model.py
if errorlevel 1 goto failed
echo PaddleOCR is ready. Start the app normally and select PaddleOCR (trial).
pause
exit /b 0
:failed
echo Setup failed. See the error above; the original app is still available.
pause
exit /b 1
