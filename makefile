# -*- makefile -*-
# $Id$
# Copyright 2013 Matthew Wall
#
# this makefile controls the build and packaging of weewx

# extract strings from setup.py to be inserted into package control files
VERSION=$(shell grep __version__ bin/weewx/__init__.py | sed -e 's/__version__=//' | sed -e 's/"//g')

CWD = $(shell pwd)
BLDDIR=build
DSTDIR=dist

all: help

help:
	@echo "options include:"
	@echo "          info  display values of variables we care about"
	@echo "       install  run the generic python install"
	@echo "       version  get version from __init__ and insert elsewhere"
	@echo ""
	@echo "     changelog  create changelog suitable for distribution"
	@echo " deb-changelog  prepend stub changelog entry for deb"
	@echo " rpm-changelog  prepend stub changelog entry for rpm"
	@echo ""
	@echo "   src-package  create source tarball suitable for distribution"
	@echo "   deb-package  create .deb package"
	@echo "   rpm-package  create .rpm package"
	@echo ""
	@echo "     deb-check  check the deb package"
	@echo "     rpm-check  check the rpm package"

info:
	@echo "     VERSION: $(VERSION)"
	@echo "         CWD: $(CWD)"

realclean:
	rm -rf build
	rm -rf dist

install:
	./setup.py --install

SRCPKG=weewx-$(VERSION).tar.gz
src-package $(DSTDIR)/$(SRCPKG): MANIFEST.in
	rm -f MANIFEST
	./setup.py sdist

# create the changelog (renamed to README.txt) for distribution
changelog:
	mkdir -p $(DSTDIR)
	pkg/mkchangelog.pl --ifile docs/changes.txt > $(DSTDIR)/README.txt

# update the version in all relevant places
version:
	for f in docs/customizing.htm docs/usersguide.htm docs/upgrading.htm; do \
          sed -e 's/Version: [0-9].*/Version: $(VERSION)/' $$f > $$f.tmp; \
          mv $$f.tmp $$f; \
        done
	sed -e 's/version =.*/version = $(VERSION)/' weewx.conf > weewx.conf.tmp; mv weewx.conf.tmp weewx.conf

DEBREVISION=1
DEBVER=$(VERSION)-$(DEBREVISION)
# add a skeleton entry to deb changelog
deb-changelog:
	pkg/mkchangelog.pl --action stub --format debian --release-version $(DEBVER) > pkg/debian/changelog.new
	cat pkg/debian/changelog >> pkg/debian/changelog.new
	mv pkg/debian/changelog.new pkg/debian/changelog

# use dpkg-buildpackage to create the debian package
# -us -uc - skip gpg signature on .dsc and .changes
# the latest version in the debian changelog must match the packaging version
DEBARCH=all
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

# run lintian on the deb package
deb-check:
	lintian -Ivi $(DSTDIR)/$(DEBPKG)

RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
# add a skeleton entry to rpm changelog
rpm-changelog:
	pkg/mkchangelog.pl --action stub --format redhat --release-version $(RPMVER) > pkg/changelog.rpm.new
	cat pkg/changelog.rpm >> pkg/changelog.rpm.new
	mv pkg/changelog.rpm.new pkg/changelog.rpm

# use rpmbuild to create the redhat package
RPMARCH=noarch
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
	cat pkg/changelog.rpm >> $(RPMBLDDIR)/SPECS/weewx.spec
	cp dist/weewx-$(VERSION).tar.gz $(RPMBLDDIR)/SOURCES
	rpmbuild -ba --clean --define '_topdir $(CWD)/$(RPMBLDDIR)' --target noarch $(CWD)/$(RPMBLDDIR)/SPECS/weewx.spec
	mkdir -p $(DSTDIR)
	mv $(RPMBLDDIR)/RPMS/$(RPMARCH)/$(RPMPKG) $(DSTDIR)
	mv $(RPMBLDDIR)/SRPMS/weewx-$(RPMVER).src.rpm $(DSTDIR)
#	rpm --addsign $(DSTDIR)/$(RPMPKG)
#	rpm --addsign $(DSTDIR)/weewx-$(RPMVER).src.rpm

# run rpmlint on the redhat package
rpm-check:
	rpmlint $(DSTDIR)/$(RPMPKG)
