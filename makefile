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
RELDIR=frs.sourceforge.net:/home/frs/project/weewx/development_versions

all: help

help: info
	@echo "options include:"
	@echo "          info  display values of variables we care about"
	@echo "       install  run the generic python install"
	@echo "       version  get version from __init__ and insert elsewhere"
	@echo ""
	@echo "        readme  create README.txt suitable for distribution"
	@echo " deb-changelog  prepend stub changelog entry for deb"
	@echo " rpm-changelog  prepend stub changelog entry for rpm"
	@echo ""
	@echo "   src-package  create source tarball suitable for distribution"
	@echo "   deb-package  create .deb package"
	@echo "   rpm-package  create .rpm package"
	@echo ""
	@echo "     check-deb  check the deb package"
	@echo "     check-rpm  check the rpm package"
	@echo "    check-docs  run weblint on the docs"
	@echo ""
	@echo "    upload-src  upload the src package"
	@echo "    upload-deb  upload the deb package"
	@echo "    upload-rpm  upload the rpm package"
	@echo " upload-readme  upload the README.txt for sourceforge"
	@echo ""
	@echo "          test  run all unit tests"
	@echo "                SUITE=path/to/foo.py to run only foo tests"

info:
	@echo "     VERSION: $(VERSION)"
	@echo "         CWD: $(CWD)"
	@echo "      RELDIR: $(RELDIR)"
	@echo "        USER: $(USER)"

realclean:
	rm -rf build
	rm -rf dist

check-docs:
	weblint docs/*.htm

# if no suite is specified, find all test suites in the source tree
ifndef SUITE
SUITE=`find bin -name "test_*.py"`
endif
test:
	@rm -f $(BLDDIR)/test-results
	@mkdir -p $(BLDDIR)
	@for f in $(SUITE); do \
  echo running $$f; \
  echo $$f >> $(BLDDIR)/test-results; \
  PYTHONPATH=bin python $$f 2>> $(BLDDIR)/test-results; \
  echo >> $(BLDDIR)/test-results; \
done
	@grep "ERROR:\|FAIL:" $(BLDDIR)/test-results || echo "no failures"
	@echo "see $(BLDDIR)/test-results"

install:
	./setup.py --install

SRCPKG=weewx-$(VERSION).tar.gz
src-package $(DSTDIR)/$(SRCPKG): MANIFEST.in
	rm -f MANIFEST
	./setup.py sdist

upload-src:
	scp $(DSTDIR)/$(SRCPKG) $(USER)@$(RELDIR)

# create the README.txt for uploading to sourceforge
README_HEADER="\
--------------------\n\
weewx packages      \n\
--------------------\n\
\n\
$(DEBPKG)\n\
   for Debian, Ubuntu, Mint\n\
\n\
$(RPMPKG)\n\
   for Redhat, CentOS, Fedora\n\
\n\
$(SRCPKG)\n\
   for all operating systems including Linux, BSD, MacOSX\n\
   this is the best choice if you intend to customize weewx\n\
\n\
--------------------\n\
weewx change history\n\
--------------------\n"
readme: docs/changes.txt
	mkdir -p $(DSTDIR)
	rm -f $(DSTDIR)/README.txt
	echo $(README_HEADER) > $(DSTDIR)/README.txt
	pkg/mkchangelog.pl --ifile docs/changes.txt >> $(DSTDIR)/README.txt

upload-readme: readme
	scp $(DSTDIR)/README.txt $(USER)@$(RELDIR)

# update the version in all relevant places
VDOCS=customizing.htm usersguide.htm upgrading.htm
version:
	for f in $(VDOCS); do \
  sed -e 's/Version: [0-9].*/Version: $(VERSION)/' docs/$$f > docs/$$f.tmp; \
  mv docs/$$f.tmp docs/$$f; \
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
check-deb:
	lintian -Ivi $(DSTDIR)/$(DEBPKG)

upload-deb:
	scp $(DSTDIR)/$(DEBPKG) $(USER)@$(RELDIR)

RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
# add a skeleton entry to rpm changelog
rpm-changelog:
	pkg/mkchangelog.pl --action stub --format redhat --release-version $(RPMVER) > pkg/changelog.rpm.new
	cat pkg/changelog.rpm >> pkg/changelog.rpm.new
	mv pkg/changelog.rpm.new pkg/changelog.rpm

# use rpmbuild to create the rpm package
RPMARCH=noarch
RPMOS=$(shell if [ -f /etc/SuSE-release ]; then echo .suse; fi)
RPMBLDDIR=$(BLDDIR)/weewx-$(RPMVER)$(RPMOS).$(RPMARCH)
RPMPKG=weewx-$(RPMVER)$(RPMOS).$(RPMARCH).rpm
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
	mv $(RPMBLDDIR)/SRPMS/weewx-$(RPMVER)$(RPMOS).src.rpm $(DSTDIR)
#	rpm --addsign $(DSTDIR)/$(RPMPKG)
#	rpm --addsign $(DSTDIR)/weewx-$(RPMVER)$(RPMOS).src.rpm

# run rpmlint on the redhat package
check-rpm:
	rpmlint $(DSTDIR)/$(RPMPKG)

upload-rpm:
	scp $(DSTDIR)/$(RPMPKG) $(USER)@$(RELDIR)

# run perlcritic to ensure clean perl code.  put these in ~/.perlcriticrc:
# [-CodeLayout::RequireTidyCode]
# [-Modules::ProhibitExcessMainComplexity]
# [-Modules::RequireVersionVar]
critic:
	perlcritic -1 --verbose 8 pkg/mkchangelog.pl
