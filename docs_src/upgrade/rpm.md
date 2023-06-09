# Upgrade RPM

These are the instructions for upgrading WeeWX that was installed from an
rpm package using `yum` or `dnf` (systems based on Redhat) or `zypper`
(systems based on SUSE).

Upgrade to the latest version like this:

```
sudo yum update weewx
```

The upgrade process will not modify the WeeWX databases.

Unmodified files will be upgraded. If modifications have been made to the
configuration, `rpm` will display a message about any differences between the
changes and the new configuration. Any new changes from the upgrade will be
noted as files with a `.rpmnew` extension and the modified files will be left
untouched.

For example, if `/etc/weewx/weewx.conf` was modified, `rpm` will present a
message something like this:

```
warning: /etc/weewx/weewx.conf created as /etc/weewx/weewx.conf.rpmnew
```
