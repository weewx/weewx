addFilter("summary-not-capitalized")
addFilter("no-manual-page-for-binary weectl")
addFilter("no-manual-page-for-binary weewxd")
addFilter("dangerous-command-in-%preun rm")
addFilter("dangerous-command-in-%pre cp")
addFilter("dangerous-command-in-%post cp")
# these are helper scripts that use /usr/bin/env
addFilter("wrong-script-interpreter .*/setup_mysql.sh")
addFilter("wrong-script-interpreter .*/i18n-report")
# logwatch stuff belongs in /etc in case logwatch not installed
addFilter("executable-marked-as-config-file /etc/weewx/logwatch/scripts/services/weewx")
