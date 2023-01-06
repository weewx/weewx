#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Install or uninstall files necessary to run as a daemon"""

import importlib.resources
import os.path
import shutil

import weecfg
import weeutil.weeutil
from weeutil.weeutil import bcolors


def daemon_install(daemon_type, config_path=None, user=None, weewxd_path=None, daemon_dir=None):
    """Install the daemon files.

    Args:
        daemon_type(str): The type of daemon file. Can be either 'sysv' or 'systemd'. Required.
        config_path(str): Path to the weewx configuration file. Default is to find it in
            the "usual places."
        user(str): The user to run as. Default is 'root'
        weewxd_path(str): Path to the weewxd executable. Default is to figure it out.
        daemon_dir(str): The directory into which the finished daemon file should be put. If
            not given, it will be determined on the basis of daemon_type.
    """
    config_path, config_dict = weecfg.read_config(config_path)

    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    if not weewxd_path:
        # We need the path to weewxd, not weewxd.py, because it contains the shebang used
        # to invoke the proper virtual environment. Otherwise, the daemon will not be able to
        # find its libraries.
        weewxd_path = shutil.which('weewxd')
        if not weewxd_path:
            # weewxd is not in the current path, perhaps because we were invoked using sudo, which
            # uses the abbreviated secure_path set in /etc/sudoers, which does not search the
            # user's home directory. Take an educated guess. First, we can only do this if we
            # have a user
            if user:
                # Now check his/her directory ~/.local:
                candidate = os.path.expanduser(f"~{user}/.local/bin/weewxd")
                if os.path.isfile(candidate):
                    # Good guess. Use it.
                    weewxd_path = candidate
    if not weewxd_path:
        raise FileNotFoundError("Could not find path to 'weewxd'")

    if daemon_type == 'systemd':
        systemd_install(config_path=config_path,
                        user=user,
                        weewxd_path=weewxd_path,
                        daemon_dir=daemon_dir)
    elif daemon_type == 'sysv':
        """To appear"""
    else:
        raise ValueError(f"Unknown daemon type: {daemon_type}")


def systemd_install(config_path=None, user=None, weewxd_path=None, daemon_dir=None):
    """Install a systemd file."""

    service_file_name = 'weewx.service'

    # We need the full path for the service file:
    config_path = os.path.abspath(config_path)

    # Get the systemd template from package resources.
    with weeutil.weeutil.path_to_resource('wee_resources', 'util') as util_path:
        systemd_template_path = os.path.join(util_path, 'systemd', service_file_name)
        # Read it all in.
        with open(systemd_template_path, 'rt') as fd:
            in_lines = fd.readlines()

    # Process it line by line, making any necessary substitutions
    out_lines = []
    for line in in_lines:
        if '=' in line:
            key, value = line.split('=')
            if user and 'User' in key:
                line = f'User={user}\n'
            elif 'ExecStart' in key:
                line = f'ExecStart={weewxd_path} {config_path}\n'
        out_lines.append(line)

    # Figure out where the finished systemd file will go.
    if not daemon_dir:
        # No idea if this is true of all systemd systems. Probably not.
        daemon_dir = '/etc/systemd/system'
    target_path = os.path.join(daemon_dir, service_file_name)

    # Now write it out
    with open(target_path, 'w') as outd:
        outd.writelines(out_lines)
    print(f"Systemd file written to {bcolors.BOLD}{target_path}{bcolors.ENDC}")


def daemon_uninstall(daemon_type=None):
    """Uninstall the daemon files

    Args:
        daemon_type(str): The type of daemon file. Can be either 'sysv' or 'systemd'.
    """
