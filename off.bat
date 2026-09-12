echo  Deleting a get IP plan...
REM 任务名称
set TASK_NAME=getIPMailVPN

REM 删除定时任务
schtasks /delete /tn "%TASK_NAME%-08" /f
schtasks /delete /tn "%TASK_NAME%-12" /f
schtasks /delete /tn "%TASK_NAME%-16" /f
schtasks /delete /tn "%TASK_NAME%-20" /f

echo Task "%TASK_NAME%" has been deleted.

pause