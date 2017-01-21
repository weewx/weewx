@echo off
@echo starting up weewx using configuration c:\Users\weewx\weewx.conf
@echo.
@echo view reports in file:///c:/Users/weewx/public_html
@echo.

set PATH=c:\python27;%PATH%
cd c:\Users\weewx
python bin\weewxd weewx.conf
