The following drivers have been checked under Python 3:

vantage.py
wmr100.py


Move `weecfg.Logger` to `weeutil.log`
Encapsulate `syslog.openlog` and `syslog.setlogmask` in the logging shim.

Need a way to specify logdbg, logerr, etc., by using a name. Something like
```
logmsg('crt', 'my message')
```

Packages that need to be updated:
* WeatherCloud