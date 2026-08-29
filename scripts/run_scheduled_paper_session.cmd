@echo off
REM Wrapper for Windows Task Scheduler.
REM
REM schtasks stores /TR verbatim, so embedding `&&` and redirections there is fragile - the caret
REM escaping survives into the stored command and the task silently does nothing. Keeping the real
REM command in a batch file means the scheduler only has to launch one path.
setlocal
cd /d D:\quant_system
if not exist logs\paper_runs mkdir logs\paper_runs
set LOGFILE=logs\paper_runs\scheduled_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%.log
echo ==== scheduled run started %DATE% %TIME% ==== >> "%LOGFILE%"
.venv\Scripts\python.exe scripts\run_scheduled_paper_session.py --universe-name NIFTY500 >> "%LOGFILE%" 2>&1
echo ==== scheduled run exited %ERRORLEVEL% at %TIME% ==== >> "%LOGFILE%"
endlocal
