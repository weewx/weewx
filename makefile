# -*- makefile -*-
# this makefile controls the build and packaging of weewx
# Copyright 2013 Matthew Wall

# if you do not want to sign the packages, set SIGN to 0
SIGN=1

# WWW server
WEEWX_COM=weewx.com

# location of the html documentation
WEEWX_HTMLDIR=/var/www/html
# location of weewx downloads
WEEWX_DOWNLOADS=$(WEEWX_HTMLDIR)/downloads
# location for staging weewx package uploads
WEEWX_STAGING=$(WEEWX_HTMLDIR)/downloads/development_versions

# extract version to be used in package controls and labels
VERSION=$(shell grep "__version__.*=" bin/weewx/__init__.py | sed -e 's/__version__=//' | sed -e 's/"//g')
# just the major.minor part of the version
MMVERSION:=$(shell echo "$(VERSION)" | sed -e 's%.[0-9a-z]*$$%%')

CWD = $(shell pwd)
BLDDIR=build
DSTDIR=dist

PYTHON=python3

all: help

help: info
	@echo "options include:"
	@echo "          info  display values of variables we care about"
	@echo "       install  run the generic python install"
	@echo "       version  get version from __init__ and insert elsewhere"
	@echo ""
	@echo "    readme.txt  create README.txt suitable for distribution"
	@echo " deb-changelog  prepend stub changelog entry for deb"
	@echo " rpm-changelog  prepend stub changelog entry for rpm"
	@echo ""
	@echo "   src-package  create source tarball suitable for distribution"
	@echo "   deb-package  create .deb package"
	@echo "   rpm-package  create .rpm package   (OSREL,RPMOS)"
	@echo ""
	@echo "     check-deb  check the deb package"
	@echo "     check-rpm  check the rpm package"
	@echo "    check-docs  run weblint on the docs"
	@echo ""
	@echo "    upload-src  upload the src package"
	@echo "    upload-deb  upload the deb package"
	@echo "   upload-rhel  upload the redhat rpm package"
	@echo "   upload-suse  upload the suse rpm package"
	@echo " upload-readme  upload the README.txt"
	@echo ""
	@echo "   upload-docs  upload docs to weewx.com"
	@echo ""
	@echo "       release  rearrange files on the download server"
	@echo ""
	@echo "          test  run all unit tests"
	@echo "                SUITE=path/to/foo.py to run only foo tests"
	@echo "    test-clean  remove test databases. recommended when switching between python 2 and 3"

info:
	@echo "     VERSION: $(VERSION)"
	@echo "   MMVERSION: $(MMVERSION)"
	@echo "         CWD: $(CWD)"
	@echo "   UPLOADDIR: $(UPLOADDIR)"
	@echo "        USER: $(USER)"
	@echo "  WWW SERVER: $(WEEWX_COM)"

clean:
	find . -name "*.pyc" -exec rm {} \;
	find . -name __pycache__ -exec rm -rf {} \;

realclean:
	rm -f MANIFEST
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
	@echo "Python interpreter in use:" >> $(BLDDIR)/test-results 2>&1;
	@$(PYTHON) -c "import sys;print(sys.executable+'\n')" >> $(BLDDIR)/test-results 2>&1;
	@for f in $(SUITE); do \
  echo running $$f; \
  echo $$f >> $(BLDDIR)/test-results; \
  PYTHONPATH="bin:examples" $(PYTHON) $$f >> $(BLDDIR)/test-results 2>&1; \
  echo >> $(BLDDIR)/test-results; \
done
	@grep "ERROR:\|FAIL:" $(BLDDIR)/test-results || echo "no failures"
	@grep "skipped=" $(BLDDIR)/test-results || echo "no tests were skipped"
	@echo "see $(BLDDIR)/test-results for output from the tests"

test-setup:
	bin/weedb/test/setup_mysql

TESTDIR=/var/tmp/weewx_test
MYSQLCLEAN="drop database test_weewx;\n\
drop database test_alt_weewx;\n\
drop database test_sim;\n\
drop database test_weewx1;\n"
test-clean:
	rm -rf $(TESTDIR)
	echo $(MYSQLCLEAN) | mysql --user=weewx --password=weewx --force >/dev/null 2>&1

install:
	./setup.py --install

SRCPKG=weewx-$(VERSION).tar.gz
src-package $(DSTDIR)/$(SRCPKG): MANIFEST.in
	rm -f MANIFEST
	./setup.py sdist

# upload the source tarball to the web site
upload-src:
	scp $(DSTDIR)/$(SRCPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# upload docs to the web site
upload-docs:
	rsync -rv docs $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)

# create the README.txt for uploading
README_HEADER="\
--------------------\n\
weewx packages      \n\
--------------------\n\
\n\
$(DEBPKG)\n\
   for Debian, Ubuntu, Mint, including Raspberry Pi\n\
\n\
weewx-$(RPMVER).el.$(RPMARCH).rpm\n\
   for Redhat, CentOS, Fedora\n\
\n\
weewx-$(RPMVER).suse.$(RPMARCH).rpm\n\
   for SuSE, OpenSuSE\n\
\n\
$(SRCPKG)\n\
   for all operating systems including Linux, BSD, MacOSX\n\
   this is the best choice if you intend to customize weewx\n\
\n\
--------------------\n\
weewx change history\n\
--------------------\n"
readme.txt: docs/changes.txt
	mkdir -p $(DSTDIR)
	rm -f $(DSTDIR)/README.txt
	echo $(README_HEADER) > $(DSTDIR)/README.txt
	pkg/mkchangelog.pl --ifile docs/changes.txt >> $(DSTDIR)/README.txt

upload-readme: readme.txt
	scp $(DSTDIR)/README.txt $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# update the version in all relevant places
VDOCS=readme.htm customizing.htm devnotes.htm hardware.htm usersguide.htm upgrading.htm utilities.htm
VCONFIGS=weewx.conf bin/weecfg/tests/expected/weewx40_user_expected.conf
version:
	for f in $(VDOCS); do \
  sed -e 's/^Version: [0-9].*/Version: $(MMVERSION)/' docs/$$f > docs/$$f.tmp; \
  mv docs/$$f.tmp docs/$$f; \
done
	for f in $(VCONFIGS); do \
  sed -e 's/version = .*/version = $(VERSION)/' $$f > $$f.tmp; \
  mv $$f.tmp $$f; \
done

DEBREVISION=1
DEBVER=$(VERSION)-$(DEBREVISION)
# add a skeleton entry to deb changelog
deb-changelog:
	if [ "`grep $(DEBVER) pkg/debian/changelog`" = "" ]; then \
  pkg/mkchangelog.pl --action stub --format debian --release-version $(DEBVER) > pkg/debian/changelog.new; \
  cat pkg/debian/changelog >> pkg/debian/changelog.new; \
  mv pkg/debian/changelog.new pkg/debian/changelog; \
fi

# use dpkg-buildpackage to create the debian package
# -us -uc - skip gpg signature on .dsc and .changes
# the latest version in the debian changelog must match the packaging version
DEBARCH=all
DEBBLDDIR=$(BLDDIR)/weewx-$(VERSION)
DEBPKG=weewx_$(DEBVER)_$(DEBARCH).deb
ifneq ("$(SIGN)","1")
DPKG_OPT=-us -uc
endif
deb-package: deb-package-python2 deb-package-python3

deb-package-prep: $(DSTDIR)/$(SRCPKG)
	mkdir -p $(BLDDIR)
	tar xfz $(DSTDIR)/$(SRCPKG) -C $(BLDDIR)
	cp -p $(DSTDIR)/$(SRCPKG) $(BLDDIR)/weewx_$(VERSION).orig.tar.gz
	rm -rf $(DEBBLDDIR)/debian
	mkdir -m 0755 $(DEBBLDDIR)/debian
	mkdir -m 0755 $(DEBBLDDIR)/debian/source
	cp pkg/debian/changelog $(DEBBLDDIR)/debian
	cp pkg/debian/compat $(DEBBLDDIR)/debian
	cp pkg/debian/conffiles $(DEBBLDDIR)/debian
	cp pkg/debian/config $(DEBBLDDIR)/debian
	cp pkg/debian/copyright $(DEBBLDDIR)/debian
	cp pkg/debian/postinst $(DEBBLDDIR)/debian
	cp pkg/debian/postrm $(DEBBLDDIR)/debian
	cp pkg/debian/preinst $(DEBBLDDIR)/debian
	cp pkg/debian/prerm $(DEBBLDDIR)/debian
	cp pkg/debian/rules $(DEBBLDDIR)/debian
	cp pkg/debian/source/format $(DEBBLDDIR)/debian/source
	cp pkg/debian/templates $(DEBBLDDIR)/debian

deb-package-python2: deb-package-prep
	cp pkg/debian/control $(DEBBLDDIR)/debian
	rm -rf $(DEBBLDDIR)/debian/weewx*
	rm -f $(DEBBLDDIR)/debian/files
	(cd $(DEBBLDDIR); dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)

deb-package-python3: deb-package-prep
	cp pkg/debian/control.python3 $(DEBBLDDIR)/debian/control
	rm -rf $(DEBBLDDIR)/debian/weewx*
	rm -f $(DEBBLDDIR)/debian/files
	(cd $(DEBBLDDIR); DEB_BUILD_OPTIONS=python3 dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)/python3-$(DEBPKG)

# run lintian on the deb package
check-deb:
	lintian -Ivi $(DSTDIR)/$(DEBPKG)

upload-deb:
	scp $(DSTDIR)/$(DEBPKG) $(DSTDIR)/python3-$(DEBPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
# add a skeleton entry to rpm changelog
rpm-changelog:
	if [ "`grep $(RPMVER) pkg/changelog.rpm`" = "" ]; then \
  pkg/mkchangelog.pl --action stub --format redhat --release-version $(RPMVER) > pkg/changelog.rpm.new; \
  cat pkg/changelog.rpm >> pkg/changelog.rpm.new; \
  mv pkg/changelog.rpm.new pkg/changelog.rpm; \
fi

# use rpmbuild to create the rpm package
# specify the operating system release target (e.g., 7 for centos7)
OSREL=7
RPMARCH=noarch
RPMOS=$(shell if [ -f /etc/SuSE-release ]; then echo .suse; else echo .el$(OSREL); fi)
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
            -e 's%RPMREVISION%$(RPMREVISION)%' \
            -e 's%OSREL%$(OSREL)%' \
            pkg/weewx.spec.in > $(RPMBLDDIR)/SPECS/weewx.spec
	cat pkg/changelog.rpm >> $(RPMBLDDIR)/SPECS/weewx.spec
	cp dist/weewx-$(VERSION).tar.gz $(RPMBLDDIR)/SOURCES
	rpmbuild -ba --clean --define '_topdir $(CWD)/$(RPMBLDDIR)' --target noarch $(CWD)/$(RPMBLDDIR)/SPECS/weewx.spec
	mkdir -p $(DSTDIR)
	mv $(RPMBLDDIR)/RPMS/$(RPMARCH)/$(RPMPKG) $(DSTDIR)
#	mv $(RPMBLDDIR)/SRPMS/weewx-$(RPMVER)$(RPMOS).src.rpm $(DSTDIR)
ifeq ("$(SIGN)","1")
	rpm --addsign $(DSTDIR)/$(RPMPKG)
#	rpm --addsign $(DSTDIR)/weewx-$(RPMVER)$(RPMOS).src.rpm
endif

redhat-packages: rpm-package-el7 rpm-package-el8

rpm-package-el7:
	make rpm-package OSREL=7

rpm-package-el8:
	make rpm-package OSREL=8

# run rpmlint on the redhat package
check-rpm:
	rpmlint $(DSTDIR)/$(RPMPKG)

upload-rpm:
	scp $(DSTDIR)/$(RPMPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

upload-rhel:
	make upload-rpm RPMOS=.el$(OSREL)

upload-suse:
	make upload-rpm RPMOS=.suse$(OSREL)

# shortcut to upload all packages from a single machine
DEB_PKG=weewx_$(DEBVER)_$(DEBARCH).deb
RHEL_PKG=weewx-$(RPMVER).el.$(RPMARCH).rpm
SUSE_PKG=weewx-$(RPMVER).suse.$(RPMARCH).rpm
upload-pkgs:
	scp $(DSTDIR)/$(DEB_PKG) $(DSTDIR)/$(RHEL_PKG) $(DSTDIR)/$(SUSE_PKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# move files from the upload directory to the release directory and set up the
# symlinks to them from the download root directory
DEVDIR=$(WEEWX_DOWNLOADS)/development_versions
RELDIR=$(WEEWX_DOWNLOADS)/released_versions
ARTIFACTS=$(DEB_PKG) $(RHEL_PKG) $(SUSE_PKG) $(SRCPKG)
release:
	ssh $(USER)@$(WEEWX_COM) "for f in $(ARTIFACTS); do if [ -f $(DEVDIR)/\$$f ]; then mv $(DEVDIR)/\$$f $(RELDIR); fi; done"
	ssh $(USER)@$(WEEWX_COM) "rm -f $(WEEWX_DOWNLOADS)/weewx*"
	ssh $(USER)@$(WEEWX_COM) "for f in $(ARTIFACTS); do if [ -f $(RELDIR)/\$$f ]; then ln -s released_versions/\$$f $(WEEWX_DOWNLOADS); fi; done"
	ssh $(USER)@$(WEEWX_COM) "if [ -f $(DEVDIR)/README.txt ]; then mv $(DEVDIR)/README.txt $(WEEWX_DOWNLOADS); fi"
	ssh $(USER)@$(WEEWX_COM) "chmod 664 $(WEEWX_DOWNLOADS)/released_versions/weewx?$(VERSION)*"

# make local copy of the published apt repository
pull-apt-repo:
	mkdir -p ~/.aptly
	rsync -arv $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly-test/ ~/.aptly

# add the latest version to the local apt repo using aptly
update-apt-repo:
	aptly repo add weewx $(DSTDIR)/$(DEBPKG)
	aptly snapshot create weewx-$(VERSION) from repo weewx
	aptly -architectures="all" publish switch squeeze weewx-$(VERSION)

# publish apt repo changes to the public weewx apt repo
push-apt-repo:
	rsync -arv ~/.aptly/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly-test

# run perlcritic to ensure clean perl code.  put these in ~/.perlcriticrc:
# [-CodeLayout::RequireTidyCode]
# [-Modules::ProhibitExcessMainComplexity]
# [-Modules::RequireVersionVar]
critic:
	perlcritic -1 --verbose 8 pkg/mkchangelog.pl

code-summary:
	cloc bin
	@for d in weecfg weedb weeutil weewx; do \
  cloc bin/$$d/tests; \
done

