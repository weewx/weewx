addFilter("summary-not-capitalized")
addFilter("no-manual-page-for-binary weectl")
addFilter("no-manual-page-for-binary weewxd")
addFilter("non-standard-gid")
addFilter("non-standard-uid")
addFilter("non-standard-dir-perm /etc/weewx.* 2775")
addFilter("non-standard-dir-perm /var/lib/weewx 2775")
addFilter("non-standard-dir-perm /var/www/html/weewx 2775")
addFilter("dangerous-command-in-%pre cp")
addFilter("dangerous-command-in-%post cp")
addFilter("dangerous-command-in-%post mv")
# these are helper scripts that use /usr/bin/env
addFilter("wrong-script-interpreter .*/setup_mysql.sh")
addFilter("wrong-script-interpreter .*/i18n-report")
# logrotation is handled by weewx
addFilter("log-files-without-logrotate .*/var/log/weewx")
# logwatch stuff belongs in /etc in case logwatch not installed
addFilter("non-executable-script /etc/weewx/logwatch/scripts/services/weewx")
addFilter("executable-marked-as-config-file /etc/weewx/logwatch/scripts/services/weewx")
