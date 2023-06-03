# -*- makefile -*-
# this makefile controls the build and packaging of weewx
# Copyright 2013 Matthew Wall

# if you do not want to sign the packages, set SIGN to 0
SIGN=1

# WWW server
WEEWX_COM:=weewx.com

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

ifndef PYTHON
PYTHON=python3
endif

all: help

help: info
	@echo "options include:"
	@echo "          info  display values of variables we care about"
	@echo "       install  run the generic python install"
	@echo "       version  get version from __init__ and insert elsewhere"
	@echo ""
	@echo "    deb-changelog prepend stub changelog entry for deb"
	@echo " redhat-changelog prepend stub changelog entry for redhat"
	@echo "   suse-changelog prepend stub changelog entry for suse"
	@echo ""
	@echo "    src-package create source tarball suitable for distribution"
	@echo "debian-packages create the debian packages"
	@echo "redhat-packages create the redhat packages"
	@echo "  suse-packages create the suse packages"
	@echo ""
	@echo "     check-deb  check the deb package"
	@echo "     check-rpm  check the rpm package"
	@echo "    check-docs  run weblint on the docs"
	@echo ""
	@echo "    upload-src  upload the src package"
	@echo " upload-debian  upload the debian deb packages"
	@echo " upload-redhat  upload the redhat rpm packages"
	@echo "   upload-suse  upload the suse rpm packages"
	@echo ""
	@echo "   upload-docs  upload docs to weewx.com"
	@echo ""
	@echo "       release  rearrange files on the download server"
	@echo ""
	@echo "          test  run all unit tests"
	@echo "                SUITE=path/to/foo.py to run only foo tests"
	@echo "    test-clean  remove test databases"
	@echo "                recommended when switching between python 2 and 3"
	@echo ""
	@echo " apt repository management"
	@echo "    pull-apt-repo"
	@echo "  update-apt-repo"
	@echo "    push-apt-repo"
	@echo ""
	@echo " yum repository management"
	@echo "    pull-yum-repo"
	@echo "  update-yum-repo"
	@echo "    push-yum-repo"
	@echo ""
	@echo " suse repository management"
	@echo "   pull-suse-repo"
	@echo " update-suse-repo"
	@echo "   push-suse-repo"
	@echo ""

info:
	@echo "     VERSION: $(VERSION)"
	@echo "   MMVERSION: $(MMVERSION)"
	@echo "      PYTHON: $(PYTHON)"
	@echo "         CWD: $(CWD)"
	@echo "        USER: $(USER)"
	@echo "   WEEWX_COM: $(WEEWX_COM)"
	@echo " STAGING_DIR: $(STAGING_DIR)"

clean:
	find . -name "*.pyc" -exec rm {} \;
	find . -name __pycache__ -exec rm -rf {} \;
	rm -rf bin/weewx.egg-info

realclean:
	rm -f MANIFEST
	rm -rf build
	rm -rf dist

check-docs:
	weblint docs/*.htm

# if no suite is specified, find all test suites in the source tree
ifndef SUITE
SUITE=`find bin examples -name "test_*.py"`
endif
test:
	@rm -f $(BLDDIR)/test-results
	@mkdir -p $(BLDDIR)
	@echo "Python interpreter in use:" >> $(BLDDIR)/test-results 2>&1;
	@$(PYTHON) -c "import sys;print(sys.executable+'\n')" >> $(BLDDIR)/test-results 2>&1;
	@for f in $(SUITE); do \
  echo running $$f; \
  echo $$f >> $(BLDDIR)/test-results; \
  PYTHONPATH="bin:examples:bin/weewx/tests" $(PYTHON) $$f >> $(BLDDIR)/test-results 2>&1; \
  echo >> $(BLDDIR)/test-results; \
done
	@grep "ERROR:\|FAIL:" $(BLDDIR)/test-results || echo "no failures"
	@grep "skipped=" $(BLDDIR)/test-results || echo "no tests were skipped"
	@echo "see $(BLDDIR)/test-results for output from the tests"
	@grep -q "ERROR:\|FAIL:" $(BLDDIR)/test-results && exit 1 || true

test-setup:
	bin/weedb/tests/setup_mysql.sh

test-setup-ci:
	MYSQL_NO_OPTS=1 bin/weedb/tests/setup_mysql.sh

TESTDIR=/var/tmp/weewx_test
MYSQLCLEAN="drop database test_weewx;\n\
drop database test_alt_weewx;\n\
drop database test_sim;\n\
drop database test_weewx1;\n\
drop database test_weewx2;\n\
drop database test_scratch;\n"

test-clean:
	rm -rf $(TESTDIR)
	echo $(MYSQLCLEAN) | mysql --user=weewx --password=weewx --force >/dev/null 2>&1

install:
	$(PYTHON) ./setup.py --install

SRCPKG=weewx-$(VERSION).tar.gz
src-package $(DSTDIR)/$(SRCPKG): MANIFEST.in
	rm -f MANIFEST
	$(PYTHON) ./setup.py sdist

# upload the source tarball to the web site
upload-src:
	scp $(DSTDIR)/$(SRCPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# upload docs to the web site
upload-docs:
	rsync -Orv docs $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/docs/$(MMVERSION)

# update the version in all relevant places
VDOCS=readme.htm customizing.htm devnotes.htm hardware.htm usersguide.htm upgrading.htm utilities.htm
VCONFIGS=weewx.conf bin/weecfg/tests/expected/weewx43_user_expected.conf
VSKINS=skins/Ftp/skin.conf skins/Mobile/skin.conf skins/Rsync/skin.conf skins/Seasons/skin.conf skins/Smartphone/skin.conf skins/Standard/skin.conf
version:
	for f in $(VDOCS); do \
  sed -e 's/^Version: [0-9].*/Version: $(MMVERSION)/' docs/$$f > docs/$$f.tmp; \
  mv docs/$$f.tmp docs/$$f; \
done
	for f in $(VCONFIGS); do \
  sed -e 's/version = [0-9].*/version = $(VERSION)/' $$f > $$f.tmp; \
  mv $$f.tmp $$f; \
done
	for f in $(VSKINS); do \
  sed -e 's/^SKIN_VERSION = [0-9].*/SKIN_VERSION = $(VERSION)/' $$f > $$f.tmp; \
  mv $$f.tmp $$f; \
done
	sed -e 's/^VERSION = .*/VERSION = "$(VERSION)"/' setup.py > setup.py.tmp
	mv setup.py.tmp setup.py
	chmod 755 setup.py

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
debian-packages: deb-package-python2 deb-package-python3

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
	cp pkg/debian/control.python2 $(DEBBLDDIR)/debian/control
	rm -f $(DEBBLDDIR)/debian/files
	rm -rf $(DEBBLDDIR)/debian/weewx*
	(cd $(DEBBLDDIR); DEB_BUILD_OPTIONS=python2 dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)/python-$(DEBPKG)

deb-package-python3: deb-package-prep
	cp pkg/debian/control.python3 $(DEBBLDDIR)/debian/control
	rm -f $(DEBBLDDIR)/debian/files
	rm -rf $(DEBBLDDIR)/debian/weewx*
	(cd $(DEBBLDDIR);  DEB_BUILD_OPTIONS=python3 dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)/python3-$(DEBPKG)

# run lintian on the deb package
check-deb:
	lintian -Ivi $(DSTDIR)/$(DEBPKG)

upload-debian:
	scp $(DSTDIR)/python-$(DEBPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)
	scp $(DSTDIR)/python3-$(DEBPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# specify the operating system release target (e.g., 7 for centos7)
OSREL=
# specify the operating system label (e.g., el, suse)
RPMOS=$(shell if [ -f /etc/SuSE-release -o -f /etc/SUSE-brand ]; then echo suse; elif [ -f /etc/redhat-release ]; then echo el; else echo os; fi)

RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
# add a skeleton entry to rpm changelog
rpm-changelog:
	if [ "`grep $(RPMVER) pkg/changelog.$(RPMOS)`" = "" ]; then \
  pkg/mkchangelog.pl --action stub --format redhat --release-version $(RPMVER) > pkg/changelog.$(RPMOS).new; \
  cat pkg/changelog.$(RPMOS) >> pkg/changelog.$(RPMOS).new; \
  mv pkg/changelog.$(RPMOS).new pkg/changelog.$(RPMOS); \
fi

# use rpmbuild to create the rpm package
# specify the architecture (always noarch)
RPMARCH=noarch
RPMBLDDIR=$(BLDDIR)/weewx-$(RPMVER).$(RPMOS)$(OSREL).$(RPMARCH)
RPMPKG=weewx-$(RPMVER).$(RPMOS)$(OSREL).$(RPMARCH).rpm
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
	cat pkg/changelog.$(RPMOS) >> $(RPMBLDDIR)/SPECS/weewx.spec
	cp dist/weewx-$(VERSION).tar.gz $(RPMBLDDIR)/SOURCES
	rpmbuild -ba --clean --define '_topdir $(CWD)/$(RPMBLDDIR)' --target noarch $(CWD)/$(RPMBLDDIR)/SPECS/weewx.spec
	mkdir -p $(DSTDIR)
	mv $(RPMBLDDIR)/RPMS/$(RPMARCH)/$(RPMPKG) $(DSTDIR)
#	mv $(RPMBLDDIR)/SRPMS/weewx-$(RPMVER).$(RPMOS)$(OSREL).src.rpm $(DSTDIR)
ifeq ("$(SIGN)","1")
	rpm --addsign $(DSTDIR)/$(RPMPKG)
#	rpm --addsign $(DSTDIR)/weewx-$(RPMVER).$(RPMOS)$(OSREL).src.rpm
endif

redhat-changelog:
	make rpm-changelog RPMOS=el

redhat-packages: rpm-package-el7 rpm-package-el8

rpm-package-el7:
	make rpm-package RPMOS=el OSREL=7

rpm-package-el8:
	make rpm-package RPMOS=el OSREL=8

suse-changelog:
	make rpm-changelog RPMOS=suse

suse-packages: rpm-package-suse12 rpm-package-suse15

rpm-package-suse12:
	make rpm-package RPMOS=suse OSREL=12

rpm-package-suse15:
	make rpm-package RPMOS=suse OSREL=15

# run rpmlint on the rpm package
check-rpm:
	rpmlint $(DSTDIR)/$(RPMPKG)

upload-rpm:
	scp $(DSTDIR)/$(RPMPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

upload-redhat:
	make upload-rpm RPMOS=el OSREL=7
	make upload-rpm RPMOS=el OSREL=8

upload-suse:
	make upload-rpm RPMOS=suse OSREL=12
	make upload-rpm RPMOS=suse OSREL=15

# shortcut to upload all packages from a single machine
DEB2_PKG=python-weewx_$(DEBVER)_$(DEBARCH).deb
DEB3_PKG=python3-weewx_$(DEBVER)_$(DEBARCH).deb
RHEL7_PKG=weewx-$(RPMVER).el7.$(RPMARCH).rpm
RHEL8_PKG=weewx-$(RPMVER).el8.$(RPMARCH).rpm
SUSE12_PKG=weewx-$(RPMVER).suse12.$(RPMARCH).rpm
SUSE15_PKG=weewx-$(RPMVER).suse15.$(RPMARCH).rpm
upload-pkgs:
	scp $(DSTDIR)/$(SRCPKG) $(DSTDIR)/$(DEB2_PKG) $(DSTDIR)/$(DEB3_PKG) $(DSTDIR)/$(RHEL7_PKG) $(DSTDIR)/$(RHEL8_PKG) $(DSTDIR)/$(SUSE12_PKG) $(DSTDIR)/$(SUSE15_PKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# move files from the upload directory to the release directory and set up the
# symlinks to them from the download root directory
DEVDIR=$(WEEWX_DOWNLOADS)/development_versions
RELDIR=$(WEEWX_DOWNLOADS)/released_versions
ARTIFACTS=$(DEB2_PKG) $(DEB3_PKG) $(RHEL7_PKG) $(RHEL8_PKG) $(SUSE12_PKG) $(SUSE15_PKG) $(SRCPKG)
release:
	ssh $(USER)@$(WEEWX_COM) "for f in $(ARTIFACTS); do if [ -f $(DEVDIR)/\$$f ]; then mv $(DEVDIR)/\$$f $(RELDIR); fi; done"
	ssh $(USER)@$(WEEWX_COM) "rm -f $(WEEWX_DOWNLOADS)/weewx*"
	ssh $(USER)@$(WEEWX_COM) "if [ -f $(RELDIR)/$(SRCPKG) ]; then ln -s released_versions/$(SRCPKG) $(WEEWX_DOWNLOADS); fi"
	ssh $(USER)@$(WEEWX_COM) "chmod 664 $(WEEWX_DOWNLOADS)/released_versions/weewx?$(VERSION)*"
	ssh $(USER)@$(WEEWX_COM) "cd $(WEEWX_HTMLDIR)/docs && ln -s $(MMVERSION) latest"

# this is only used when creating a new apt repository from scratch
# the .html and .list files are not part of an official apt repository.  they
# are included to make the repository self-documenting.
apt-repo:
	aptly repo create -distribution=squeeze -component=main -architectures=all python2-weewx
	aptly repo create -distribution=buster -component=main -architectures=all python3-weewx
	mkdir -p ~/.aptly/public
	cp -p pkg/index-apt.html ~/.aptly/public/index.html
	cp -p pkg/weewx-python2.list ~/.aptly/public
	cp -p pkg/weewx-python3.list ~/.aptly/public
# this is for backward-compatibility when there was not python2/3 distinction
	cp -p pkg/weewx-python2.list ~/.aptly/public/weewx.list
# these are for backward-compatibility for users that do not have python2 or
# python3 in the paths in their .list file - default to python2
	ln -s python2/dists ~/.aptly/public
	ln -s python2/pool ~/.aptly/public

# make local copy of the published apt repository
pull-apt-repo:
	mkdir -p ~/.aptly
	rsync -Oarvz $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly/ ~/.aptly

# add the latest version to the local apt repo using aptly
update-apt-repo:
	aptly repo add python2-weewx $(DSTDIR)/python-$(DEBPKG)
	aptly snapshot create python-weewx-$(DEBVER) from repo python2-weewx
	aptly publish drop squeeze python2
	aptly publish -architectures=all snapshot python-weewx-$(DEBVER) python2
# i would prefer to just do a switch, but that does not work. idkw
#	aptly publish switch squeeze python2 python-weewx-$(DEBVER)
	aptly repo add python3-weewx $(DSTDIR)/python3-$(DEBPKG)
	aptly snapshot create python3-weewx-$(DEBVER) from repo python3-weewx
	aptly publish drop buster python3
	aptly publish -architectures=all snapshot python3-weewx-$(DEBVER) python3
#	aptly publish switch buster python3 python3-weewx-$(DEBVER)

# publish apt repo changes to the public weewx apt repo
push-apt-repo:
	find ~/.aptly -type f -exec chmod 664 {} \;
	find ~/.aptly -type d -exec chmod 2775 {} \;
	rsync -Ortlvz ~/.aptly/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly-test

# copy the testing repository onto the production repository
release-apt-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz /var/www/html/aptly-test/ /var/www/html/aptly"

YUM_REPO=~/.yum/weewx
yum-repo:
	mkdir -p $(YUM_REPO)/{el7,el8}/RPMS
	cp -p pkg/index-yum.html ~/.yum/index.html
	cp -p pkg/weewx-el7.repo ~/.yum
	cp -p pkg/weewx-el8.repo ~/.yum

pull-yum-repo:
	mkdir -p $(YUM_REPO)
	rsync -Oarvz $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/yum/ ~/.yum

update-yum-repo:
	cp -p $(DSTDIR)/weewx-$(RPMVER).el7.$(RPMARCH).rpm $(YUM_REPO)/el7/RPMS
	createrepo $(YUM_REPO)/el7
	cp -p $(DSTDIR)/weewx-$(RPMVER).el8.$(RPMARCH).rpm $(YUM_REPO)/el8/RPMS
	createrepo $(YUM_REPO)/el8

push-yum-repo:
	find ~/.yum -type f -exec chmod 664 {} \;
	find ~/.yum -type d -exec chmod 2775 {} \;
	rsync -Ortlvz ~/.yum/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/yum-test

# copy the testing repository onto the production repository
release-yum-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz /var/www/html/yum-test/ /var/www/html/yum"

SUSE_REPO=~/.suse/weewx
suse-repo:
	mkdir -p $(SUSE_REPO)/{suse12,suse15}/RPMS
	cp -p pkg/index-suse.html ~/.suse/index.html
	cp -p pkg/weewx-suse12.repo ~/.suse
	cp -p pkg/weewx-suse15.repo ~/.suse

pull-suse-repo:
	mkdir -p $(SUSE_REPO)
	rsync -Oarvz $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/suse/ ~/.suse

update-suse-repo:
	cp -p $(DSTDIR)/weewx-$(RPMVER).suse12.$(RPMARCH).rpm $(SUSE_REPO)/suse12/RPMS
	createrepo $(SUSE_REPO)/suse12
	cp -p $(DSTDIR)/weewx-$(RPMVER).suse15.$(RPMARCH).rpm $(SUSE_REPO)/suse15/RPMS
	createrepo $(SUSE_REPO)/suse15

push-suse-repo:
	find ~/.suse -type f -exec chmod 664 {} \;
	find ~/.suse -type d -exec chmod 2775 {} \;
	rsync -Ortlvz ~/.suse/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/suse-test

# copy the testing repository onto the production repository
release-suse-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz /var/www/html/suse-test/ /var/www/html/suse"

# shortcuts to upload everything.  assumes that the assets have been staged
# to the local 'dist' directory.
upload-all: upload-docs upload-pkgs

# shortcut to release everything.  assumes that all of the assets have been
# staged to the development area on the distribution server.
release-all: release release-apt-repo release-yum-repo release-suse-repo

# run perlcritic to ensure clean perl code.  put these in ~/.perlcriticrc:
# [-CodeLayout::RequireTidyCode]
# [-Modules::ProhibitExcessMainComplexity]
# [-Modules::RequireVersionVar]
critic:
	perlcritic -1 --verbose 8 pkg/mkchangelog.pl

code-summary:
	cloc --force-lang="HTML",tmpl --force-lang="INI",conf --force-lang="INI",inc bin docs examples skins util
