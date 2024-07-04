#!/bin/sh
#
# Install files that integrate WeeWX into an operating system.
# This script must be run using sudo, or as root.
#
set -e

HOMEDIR=$HOME
if [ "$SUDO_USER" != "" ]; then
    HOMEDIR=$(getent passwd $SUDO_USER | cut -d: -f6)
fi
UTIL_ROOT=$HOMEDIR/weewx-data/util

if [ "$(id -u)" != "0" ]; then
  echo "This script requires admin privileges.  Use 'sudo' or run as root."
  exit 1
fi

ts=`date +"%Y%m%d%H%M%S"`

copy_file() {
    src=$1
    dst=$2
    if [ -f "$dst" ]; then
	mv ${dst} ${dst}.${ts}
    fi
    echo "Installing $dst"
    cp $src $dst
}

remove_file() {
    dst=$1
    if [ -f "$dst" ]; then
        echo "Removing $dst"
	rm $dst
    fi
}

install_udev() {
    if [ -d /etc/udev/rules.d ]; then
	copy_file $UTIL_ROOT/udev/rules.d/weewx.rules /etc/udev/rules.d/60-weewx.rules
	echo "    If you are using a device that is connected to the computer by USB or"
	echo "    serial port, unplug the device then plug it back in again to ensure that"
	echo "    permissions are applied correctly."
    fi
}

uninstall_udev() {
    remove_file /etc/udev/rules.d/60-weewx.rules
}

install_systemd() {
    copy_file $UTIL_ROOT/systemd/weewx.service /etc/systemd/system/weewx.service
    copy_file $UTIL_ROOT/systemd/weewx@.service /etc/systemd/system/weewx@.service

    echo "Reloading systemd"
    systemctl daemon-reload
    echo "Enabling weewx to start when system boots"
    systemctl enable weewx
        
    echo "You can start/stop weewx with the following commands:"
    echo "  sudo systemctl start weewx"
    echo "  sudo systemctl stop weewx"
}

uninstall_systemd() {
    echo "Stopping weewx"
    systemctl stop weewx
    echo "Disabling weewx"
    systemctl disable weewx
    remove_file /etc/systemd/system/weewx@.service
    remove_file /etc/systemd/system/weewx.service
}

install_sysv() {
    if [ -d /etc/default ]; then
        copy_file $UTIL_ROOT/default/weewx /etc/default/weewx
    fi
    copy_file $UTIL_ROOT/init.d/weewx-multi /etc/init.d/weewx
    chmod 755 /etc/init.d/weewx

    echo "Enabling weewx to start when system boots"
    update-rc.d weewx defaults

    echo "You can start/stop weewx with the following commands:"
    echo "  /etc/init.d/weewx start"
    echo "  /etc/init.d/weewx stop"
}

uninstall_sysv() {
    echo "Stopping weewx"
    /etc/init.d/weewx stop
    echo "Disabling weewx"
    update-rc.d weewx remove
    remove_file /etc/init.d/weewx
    remove_file /etc/default/weewx
}

install_bsd() {
    copy_file $UTIL_ROOT/init.d/weewx.bsd /usr/local/etc/rc.d/weewx
    chmod 755 /usr/local/etc/rc.d/weewx

    echo "Enabling weewx to start when system boots"
    sysrc weewx_enable="YES"

    echo "You can start/stop weewx with the following commands:"
    echo "  sudo service weewx start"
    echo "  sudo service weewx stop"
}

uninstall_bsd() {
    echo "Stopping weewx..."
    service weewx stop
    echo "Disabling weewx..."
    sysrc weewx_enable="NO"
    remove_file /usr/local/etc/rc.d/weewx
}

install_macos() {
    copy_file $UTIL_ROOT/launchd/com.weewx.weewxd.plist /Library/LaunchDaemons

    echo "You can start/stop weewx with the following commands:"
    echo "  sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist"
    echo "  sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist"
}

uninstall_macos() {
    echo "Stopping weewx"
    launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    remove_file /Library/LaunchDaemons/com.weewx.weewxd.plist
}

# check for systemd and/or sysV init files that might affect the init setup
# that we install.  no need to check for the files that we install, since we
# move aside any direct conflicts.
check_init() {
    init_system=$1
    files_to_check="/etc/init.d/weewx-multi"
    if [ "$init_system" = "systemd" ]; then
        files_to_check="$files_to_check /etc/init.d/weewx"
    elif [ "$init_system" = "init" ]; then
        files_to_check="$files_to_check /etc/systemd/system/weewx.service"
    fi
    files=""
    for f in $files_to_check; do
        if [ -f $f ]; then
            files="$files $f"
        fi
    done
    if [ "$files" != "" ]; then
        echo "The following files might interfere with the init configuration:"
        for f in $files; do
            echo "  $f"
        done
    fi
}


do_install() {
    init_system=$1
    echo "Set up the files necessary to run WeeWX at system startup."

    if [ ! -d $UTIL_ROOT ]; then
        echo "Cannot find utility files at location '$UTIL_ROOT'"
        exit 1
    fi

    echo "Copying files from $UTIL_ROOT"

    if [ -d /usr/local/etc/rc.d ]; then
        install_bsd
    elif [ "$init_system" = "/sbin/launchd" ]; then
        install_macos
    elif [ "$init_system" = "systemd" ]; then
        install_udev
        install_systemd
        check_init $init_system
    elif [ "$init_system" = "init" ]; then
        install_udev
        install_sysv
        check_init $init_system
    else
        echo "Unrecognized platform with init system $init_system"
    fi
}

do_uninstall() {
    init_system=$1
    echo "Remove the files for running WeeWX at system startup."

    if [ -d /usr/local/etc/rc.d ]; then
        uninstall_bsd
    elif [ "$init_system" = "/sbin/launchd" ]; then
        uninstall_macos
    elif [ "$init_system" = "systemd" ]; then
        uninstall_systemd
        uninstall_udev
    elif [ "$init_system" = "init" ]; then
        uninstall_sysv
        uninstall_udev
    else
        echo "Unrecognized platform with init system $init_system"
    fi
}

pid1=$(ps -p 1 -o comm=)
ACTION=$1
if [ "$ACTION" = "" -o "$ACTION" = "install" ]; then
    do_install $pid1
elif [ "$ACTION" = "uninstall" ]; then
    do_uninstall $pid1
fi
