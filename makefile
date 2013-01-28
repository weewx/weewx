# -*- makefile -*-
# $Id$
# Copyright 2013 Matthew Wall
#
# this makefile controls the build and packaging of weewx
#
# supported installation methods:
#
#   setup.py install
#
#   setup.py install prefix=/opt/weewx-x.y.z
#
#   sudo apt-get install weewx
#
#   sudo yum install weewx
#
# design notes:
#
# - setup.py keeps track of weewx bits
#
# - setup.py knows about locations for various layouts
#
# - makefile keeps track of per-package bits and how to put them together
#
# - platform-specific packages (deb, rpm) keep track of additional dependencies
#   such as apache and rc snippets
#
# configuration prompts:
# - location (city, state - get default from environment?)
# - lat/lon
# - altitude
# - station_type
#
# there are a zillion ways to build a debian package.  first tried dpkg (uses
# DEBIAN dir and is fairly low-level) but that did not create the changes and
# is not the tool for maintainers.  then dried dpkg-buildpackage which is a
# higher level tool (uses debian dir) but misses the config and templates.l
#
# gpg --gen-key
# gpg --list-keys
#
# ~/.rpmmacros
# %_signature gpg
# %_gpg_name  Matthew Wall
#
# what to test on debian:
#  install, upgrade, remove, purge
#
# deb install:
# apt-get install python-serial
# apt-get install python-usb
# apt-get install weewx
#
# redhat install:
# yum install weewx
# yum install weewx --nogpgcheck
#
# manual install:
# yum install pyserial
# yum install pyusb
# setup.py
#
# TODO:
# config-vp -> config-vantage
# weewxd.py -> wee.py
# config-database.py -> wee-config-database.py

# extract strings from setup.py to be inserted into package control files
VERSION=$(shell grep __version__ bin/weewx/__init__.py | sed -e 's/__version__=//' | sed -e 's/"//g')

CWD = $(shell pwd)
BLDDIR=build
DSTDIR=dist

all: help

help:
	@echo "options include:"
	@echo "         info   display values of variables we care about"
	@echo "      install   run the generic python install"
	@echo "    changelog   create changelog suitable for distribution"
	@echo "  src-package   create source tarball suitable for distribution"
	@echo "  deb-package   create .deb package"
	@echo "  rpm-package   create .rpm package"

info:
	@echo "     VERSION: $(VERSION)"
	@echo "         CWD: $(CWD)"

realclean:
	rm -rf build
	rm -rf dist

install:
	setup.py --install

SRCPKG=weewx-$(VERSION).tar.gz
src-package $(DSTDIR)/$(SRCPKG): MANIFEST.in
	setup.py sdist

# create the changelog (renamed to README.txt) for distribution
changelog:
	mkdir -p $(DSTDIR)
	pkg/mkchangelog.pl --ifile docs/changes.txt > $(DSTDIR)/README.txt

# use dpkg-buildpackage to create the debian package
# -us -uc - skip gpg signature on .dsc and .changes
# the latest version in the debian changelog must match the packaging version
DEBARCH=all
DEBREVISION=1
DEBBLDDIR=$(BLDDIR)/weewx-$(VERSION)
DEBPKG=weewx_$(VERSION)-$(DEBREVISION)_$(DEBARCH).deb
DPKG_OPT=-us -uc
deb-package: $(DSTDIR)/$(SRCPKG)
	mkdir -p $(BLDDIR)
	cp $(DSTDIR)/$(SRCPKG) $(BLDDIR)
	(cd $(BLDDIR); tar xvfz $(SRCPKG))
	(cd $(BLDDIR); mv $(SRCPKG) weewx_$(VERSION).orig.tar.gz)
	rm -rf $(DEBBLDDIR)/debian
	mkdir -m 0755 $(DEBBLDDIR)/debian
	mkdir -m 0755 $(DEBBLDDIR)/debian/source
	cp pkg/debian/changelog $(DEBBLDDIR)/debian
	cp pkg/debian/conffiles $(DEBBLDDIR)/debian
	cp pkg/debian/config $(DEBBLDDIR)/debian
	cp pkg/debian/control $(DEBBLDDIR)/debian
	cp pkg/debian/copyright $(DEBBLDDIR)/debian
	cp pkg/debian/postinst $(DEBBLDDIR)/debian
	cp pkg/debian/postrm $(DEBBLDDIR)/debian
	cp pkg/debian/prerm $(DEBBLDDIR)/debian
	cp pkg/debian/rules $(DEBBLDDIR)/debian
	cp pkg/debian/source/format $(DEBBLDDIR)/debian/source
	cp pkg/debian/templates $(DEBBLDDIR)/debian
	(cd $(DEBBLDDIR); dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)
	@echo "to verify the package run this:"
	@echo "lintian -Ivi $(DSTDIR)/$(DEBPKG)"

# use rpmbuild to create the redhat package
RPMARCH=noarch
RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
RPMBLDDIR=$(BLDDIR)/weewx-$(RPMVER)_$(RPMARCH)
RPMPKG=weewx-$(RPMVER).$(RPMARCH).rpm
rpm-package: $(DSTDIR)/$(SRCPKG)
	rm -rf $(RPMBLDDIR)
	mkdir -p -m 0755 $(RPMBLDDIR)
	mkdir -p -m 0755 $(RPMBLDDIR)/BUILD
	mkdir -p -m 0755 $(RPMBLDDIR)/BUILDROOT
	mkdir -p -m 0755 $(RPMBLDDIR)/RPMS
	mkdir -p -m 0755 $(RPMBLDDIR)/SOURCES
	mkdir -p -m 0755 $(RPMBLDDIR)/SPECS
	mkdir -p -m 0755 $(RPMBLDDIR)/SRPMS
	sed -e 's%Version:.*%Version: $(VERSION)%' \
            pkg/weewx.spec.in > $(RPMBLDDIR)/SPECS/weewx.spec
	cp dist/weewx-$(VERSION).tar.gz $(RPMBLDDIR)/SOURCES
	rpmbuild -ba --clean --define '_topdir $(CWD)/$(RPMBLDDIR)' --target noarch $(CWD)/$(RPMBLDDIR)/SPECS/weewx.spec
	mkdir -p $(DSTDIR)
	mv $(RPMBLDDIR)/RPMS/$(RPMARCH)/$(RPMPKG) $(DSTDIR)
	mv $(RPMBLDDIR)/SRPMS/weewx-$(RPMVER).src.rpm $(DSTDIR)
#	rpm --addsign $(DSTDIR)/$(RPMPKG)
#	rpm --addsign $(DSTDIR)/weewx-$(RPMVER).src.rpm
	@echo "to verify the package run this:"
	@echo "rpmlint $(DSTDIR)/$(RPMPKG)"
