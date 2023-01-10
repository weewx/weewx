# The utility **weectl**

This is a guide to the utility `weectl`. As of version 5.0, this utility has three "subcommands",
each with its own set of "actions". Eventually, it will subsume more and more of the functionality
of the other utilities.

[`weectl station`](../weectl/station) : The creation, initialization, and reconfiguration of "user data" areas.

[`weectl daemon`](../weectl/daemon) : The installation and uninstallation of files necessary to run `weewxd` as a daemon.

[`weectl extension`](../weectl/extension) : The installation and uninstallation of extensions.

Running `weectl --help` will give an overview of its subcommands:

```shell
% weectl --help        
usage: weectl -v|--version
       weectl -h|--help
       weectl station --help
       weectl daemon --help
       weectl extension --help

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit

Available subcommands:
  {station,daemon,extension}
    station             Create, modify, or upgrade a config file
    daemon              Install or uninstall a daemon file
    extension           Install, uninstall, or list extensions
```
