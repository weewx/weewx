# Upgrade RPM

If you have specified the WeeWX yum repository in
`/etc/yum.repos.d/weewx.repo`, then upgrade to the latest version like this:

```
sudo yum update weewx
```

Otherwise, download the latest X.Y.Z RPM package from the
<a href="https://weewx.com/downloads/">WeeWX downloads</a>, then
upgrade like this:

```
sudo rpm -U weewx-X.Y.Z-R.rpm
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
