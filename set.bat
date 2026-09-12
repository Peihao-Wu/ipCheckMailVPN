echo Creating a get IP plan...
REM TASK_NAME
set TASK_NAME=getIPMailVPN

REM CURRENT_DIR
set CURRENT_DIR=%~dp0

REM 1time / 4 h
schtasks /create /tn "%TASK_NAME%-08" /tr "%CURRENT_DIR%hiderun.vbs" /sc daily /st 08:00 /f
schtasks /create /tn "%TASK_NAME%-12" /tr "%CURRENT_DIR%hiderun.vbs" /sc daily /st 12:00 /f
schtasks /create /tn "%TASK_NAME%-16" /tr "%CURRENT_DIR%hiderun.vbs" /sc daily /st 16:00 /f
schtasks /create /tn "%TASK_NAME%-20" /tr "%CURRENT_DIR%hiderun.vbs" /sc daily /st 20:00 /f

echo Tasks have been created to run at 08:00, 12:00, 16:00, and 20:00.

pause