# weectl debug

Use the `weectl` subcommand `debug` to produce information about your
environment.

Specify `--help` to see how it is used:

    weectl debug --help

## Create debug information

    weectl debug 
        [--config=FILENAME] [--output=FILENAME]

Troubleshooting problems when running WeeWX often involves analysis of a number
of pieces of seemingly disparate system and WeeWX related information. The
`weectl debug` command gathers all this information together into a single output
to make troubleshooting easier. The command is particularly useful
for new users as the output may be redirected to a file then emailed or posted
to a forum to assist in remote troubleshooting.

The utility produces two types of information:

1. General information about your environment. This includes:
    - System information,
    - Load information,
    - Driver type,
    - Any installed extensions, and
    - Information about your databse

2. An obfuscated copy of your configuration file (nominally, `weewx.conf`).

!!! Warning 
    The `weectl debug` output includes a copy of the WeeWX config file
    (typically `weewx.conf`) and whilst the utility attempts to obfuscate any
    personal or sensitive information, the user should check the output
    carefully for any remaining personal or sensitive information before 
    emailing or posting the output publicly.

## Options

### --config=FILENAME

The utility is pretty good about guessing where the configuration file is,
but if you have an unusual installation or multiple stations, you may have to
tell it explicitly. You can do this using the `--config` option. For example,

    weectl debug --config=/etc/weewx/alt_config.conf

### --output=FILENAME

By default, `weectl debug` writes to standard output (the console). However,
the output can be sent somewhere else using option `--output`. For example,
to send it to `/var/tmp/weewx.info`:

    weectl debug --output=/var/tmp/weewx.info

