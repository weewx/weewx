#!/bin/sh
#
# Install the bash completion for weectl.
#
# Run it without privileges to install the completion for yourself:
#
#   sh ~/weewx-data/scripts/setup-bash-completion.sh
#
# Run it with sudo to install the completion for every user on the system:
#
#   sudo sh ~/weewx-data/scripts/setup-bash-completion.sh
#
# Add 'uninstall' to remove it again.
#
set -e

HOMEDIR=$HOME
if [ "$SUDO_USER" != "" ]; then
    if [ -d /Users/$SUDO_USER ]; then
        HOMEDIR=/Users/$SUDO_USER
    else
        HOMEDIR=$(getent passwd $SUDO_USER | cut -d: -f6)
    fi
fi
UTIL_ROOT=$HOMEDIR/weewx-data/util

ts=`date +"%Y%m%d%H%M%S"`

# Where the completion goes. Installing it as the name of the command means
# bash-completion loads it the first time the user types 'weectl', so there is
# nothing to source and nothing to add to .bashrc.
if [ "$(id -u)" = "0" ]; then
    if [ -d /usr/share/bash-completion/completions ]; then
        DST_DIR=/usr/share/bash-completion/completions
    else
        # bash-completion older than v2, or not installed
        DST_DIR=/etc/bash_completion.d
    fi
else
    DST_DIR=${XDG_DATA_HOME:-$HOMEDIR/.local/share}/bash-completion/completions
fi
DST=$DST_DIR/weectl

do_install() {
    src=$UTIL_ROOT/bash_completion.d/weectl
    if [ ! -f "$src" ]; then
        echo "Cannot find the completion file at location '$src'"
        exit 1
    fi
    mkdir -p $DST_DIR
    if [ -f "$DST" ]; then
        mv ${DST} ${DST}.${ts}
    fi
    echo "Installing $DST"
    cp $src $DST
    chmod 644 $DST
    echo "    Completion will be available in new shells. To use it in this one:"
    echo "        source $DST"
}

do_uninstall() {
    if [ -f "$DST" ]; then
        echo "Removing $DST"
        rm $DST
    else
        echo "Nothing to remove at $DST"
    fi
}

ACTION=$1
if [ "$ACTION" = "" -o "$ACTION" = "install" ]; then
    do_install
elif [ "$ACTION" = "uninstall" ]; then
    do_uninstall
else
    echo "Usage: $0 [install|uninstall]"
    exit 1
fi
