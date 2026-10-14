echo off

if not %1=="" goto start

cls

echo **************************************************************
echo SYNTAX
echo      patch197 [installation path]
echo.
echo For example, to patch dos4gw.exe in c:\TIECD directory, type:
echo.
echo      patch197 c:\TIECD
echo **************************************************************

goto end

:start

copy dos4gw.197 %1\dos4gw.exe

:end
