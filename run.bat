%echo off
call activate otheruse_env
cd /d %~dp0
for %%f in (*.py) do (
    python "%%f"
    exit /b
)