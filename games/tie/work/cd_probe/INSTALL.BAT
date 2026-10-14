echo off

if not %1=="" goto start

cls

echo **************************************************************
echo SYNTAX
echo      install [drive letter]:
echo.
echo For example, to install to the C drive, you would type:
echo.
echo      install c:
echo **************************************************************

goto end

:start

mkdir %1\tiecd
copy tie.cd %1\
mkdir %1\tiecd\resource
mkdir %1\tiecd\mission
mkdir %1\tiecd\cp320
mkdir %1\tiecd\cp640
mkdir %1\tiecd\res320
mkdir %1\tiecd\res640
cd ..
copy *.exe %1\tiecd
copy *.fnt %1\tiecd
copy *.dat %1\tiecd
copy *.pac %1\tiecd
copy *.tfr %1\tiecd
copy read.me %1\tiecd
erase %1\tiecd\cdrom.cfg
copy instrec.cfg %1\tiecd\install.cfg
copy resource\*.* %1\tiecd\resource
copy mission\*.* %1\tiecd\mission
copy cp320\*.* %1\tiecd\cp320
copy cp640\*.* %1\tiecd\cp640
copy res320\*.* %1\tiecd\res320
copy res640\*.* %1\tiecd\res640
%1
cd \tiecd
imuse.exe

:end
