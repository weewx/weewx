# The utility **weectl**

This is a guide to the utility `weectl`. As of version 5.0, this utility has two "subcommands",
each with its own set of "actions". Eventually, it will subsume more and more of the functionality
of the other utilities.

[`weectl station`](../weectl/station) : The creation, initialization, reconfiguration, and upgrading of "user data" areas.

[`weectl extension`](../weectl/extension) : The installation and uninstallation of extensions.

Running `weectl --help` will give an overview of its subcommands:

```shell
% weectl --help        
usage: weectl -v|--version
       weectl -h|--help
       weectl station --help
       weectl extension --help

optional arguments:
  -h, --help           show this help message and exit
  -v, --version        show program name and version number and exit

Available subcommands:
  {station,extension}
    station            Create, modify, or upgrade a configuration file
    extension          List, install, or uninstall extensions
```
