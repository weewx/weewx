# The utility **weectl**

This utility has two subcommands, each with its own set of actions.

[`weectl station`](../weectl/station) : Create, initialize, reconfigure, and
upgrade the configuration data that control how weewx interacts with the
station hardware, manipulates data, and generates reports.

[`weectl extension`](../weectl/extension) : List, install, and uninstall
extensions to WeeWX.

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
