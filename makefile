# -*- makefile -*-
# this makefile controls the build and packaging of weewx
# Copyright 2013-2024 Matthew Wall

# if you do not want to sign the packages, set SIGN to 0
SIGN=1

# the WeeWX WWW server
WEEWX_COM:=weewx.com
# location of the html documentation on the WWW server
WEEWX_HTMLDIR=/var/www/html
# location of weewx downloads
WEEWX_DOWNLOADS=$(WEEWX_HTMLDIR)/downloads
# location for staging weewx package uploads
WEEWX_STAGING=$(WEEWX_HTMLDIR)/downloads/development_versions

# Directory for artifacts created during the build process
BLDDIR=build
# Directory for completed files that will be tested and/or distributed
DSTDIR=dist
# Location of doc sources
DOC_SRC=docs_src
# Location of built docs
DOC_BUILT=$(BLDDIR)/docs
# Location of the skins
SKINLOC=src/weewx_data/skins

CWD=$(shell pwd)
# the current version is extracted from the pyproject.toml file
VERSION:=$(shell sed -ne 's/^version = "\(.*\)"/\1/p;' pyproject.toml)
# just the major.minor part of the version
MMVERSION:=$(shell echo "$(VERSION)" | sed -e 's%.[0-9a-z]*$$%%')

SRCPKG=weewx-$(VERSION).tgz
WHEELSRC=weewx-$(VERSION).tar.gz
WHEEL=weewx-$(VERSION)-py3-none-any.whl

PYTHON?=python3

TMPDIR?=/var/tmp

all: help

help: info
	@echo "options include:"
	@echo "          info  display values of variables we care about"
	@echo "       version  get version from pyproject.toml and insert elsewhere"
	@echo ""
	@echo "          test  run all unit tests"
	@echo "                SUITE=path/to/foo.py to run only foo tests"
	@echo "    test-clean  remove test databases"
	@echo ""
	@echo "    build-docs  build the docs using mkdocs"
	@echo "   upload-docs  upload docs to $(WEEWX_COM)"
	@echo "    check-docs  run weblint on the docs"
	@echo ""
	@echo " debian-changelog  prepend stub changelog entry for debian"
	@echo " redhat-changelog  prepend stub changelog entry for redhat"
	@echo "   suse-changelog  prepend stub changelog entry for suse"
	@echo ""
	@echo "  pypi-package  create wheel and source tarball for pypi"
	@echo "debian-package  create the debian package(s)"
	@echo "redhat-package  create the redhat package(s)"
	@echo "  suse-package  create the suse package(s)"
	@echo ""
	@echo "  check-debian  check the debian package"
	@echo "  check-redhat  check the redhat package"
	@echo "    check-suse  check the suse package"
	@echo ""
	@echo "    upload-src  upload the src package to $(WEEWX_COM)"
	@echo "   upload-pypi  upload wheel and src package to pypi.org"
	@echo " upload-debian  upload the debian deb package"
	@echo " upload-redhat  upload the redhat rpm packages"
	@echo "   upload-suse  upload the suse rpm packages"
	@echo ""
	@echo "       release  promote staged files on the download server"
	@echo ""
	@echo " apt repository management"
	@echo "    pull-apt-repo"
	@echo "  update-apt-repo"
	@echo "    push-apt-repo"
	@echo " release-apt-repo"
	@echo ""
	@echo " yum repository management"
	@echo "    pull-yum-repo"
	@echo "  update-yum-repo"
	@echo "    push-yum-repo"
	@echo " release-yum-repo"
	@echo ""
	@echo " suse repository management"
	@echo "    pull-suse-repo"
	@echo "  update-suse-repo"
	@echo "    push-suse-repo"
	@echo " release-suse-repo"
	@echo ""

info:
	@echo "       VERSION: $(VERSION)"
	@echo "     MMVERSION: $(MMVERSION)"
	@echo "        PYTHON: $(PYTHON)"
	@echo "           CWD: $(CWD)"
	@echo "          USER: $(USER)"
	@echo "     WEEWX_COM: $(WEEWX_COM)"
	@echo " WEEWX_STAGING: $(WEEWX_STAGING)"
	@echo "       DOC_SRC: $(DOC_SRC)"
	@echo "     DOC_BUILT: $(DOC_BUILT)"
	@echo "       SKINLOC: $(SKINLOC)"
	@echo ""

clean:
	find src -name "*.pyc" -exec rm {} \;
	find src -name "__pycache__" -prune -exec rm -rf {} \;
	rm -rf $(BLDDIR) $(DSTDIR)


###############################################################################
# update the version in all relevant places
VCONFIGS=src/weewx_data/weewx.conf src/weecfg/tests/expected/weewx43_user_expected.conf
VSKINS=Ftp/skin.conf Mobile/skin.conf Rsync/skin.conf Seasons/skin.conf Smartphone/skin.conf Standard/skin.conf
version:
	sed -e "s/^site_name.*/site_name: \'WeeWX $(MMVERSION)\'/" mkdocs.yml > mkdocs.yml.tmp; mv mkdocs.yml.tmp mkdocs.yml
	for f in $(VCONFIGS); do \
  sed -e 's/version = [0-9].*/version = $(VERSION)/' $$f > $$f.tmp; \
  mv $$f.tmp $$f; \
done
	for f in $(VSKINS); do \
  sed -e 's/^SKIN_VERSION = [0-9].*/SKIN_VERSION = $(VERSION)/' $(SKINLOC)/$$f > $(SKINLOC)/$$f.tmp; \
  mv $(SKINLOC)/$$f.tmp $(SKINLOC)/$$f; \
done
	sed -e 's/__version__ *=.*/__version__ = "$(VERSION)"/' src/weewx/__init__.py > weeinit.py.tmp
	mv weeinit.py.tmp src/weewx/__init__.py


###############################################################################
## testing targets

# if no suite is specified, find all test suites in the source tree
SUITE?=`find src -name "test_*.py"`
test: src/weewx_data/
	@rm -f $(BLDDIR)/test-results
	@mkdir -p $(BLDDIR)
	@echo "Python interpreter and version in use:" >> $(BLDDIR)/test-results 2>&1;
	@$(PYTHON) -c "import sys;print(sys.executable)" >> $(BLDDIR)/test-results 2>&1;
	@$(PYTHON) -V >> $(BLDDIR)/test-results 2>&1;
	@echo "----" >> $(BLDDIR)/test-results 2>&1;

	@for f in $(SUITE); do \
  echo running $$f; \
  echo $$f >> $(BLDDIR)/test-results; \
  PYTHONPATH="src:src/weewx_data/examples:src/weewx/tests" $(PYTHON) $$f >> $(BLDDIR)/test-results 2>&1; \
  echo >> $(BLDDIR)/test-results; \
done
	@grep "ERROR:\|FAIL:" $(BLDDIR)/test-results || echo "no failures"
	@grep "skipped=" $(BLDDIR)/test-results || echo "no tests were skipped"
	@echo "see $(BLDDIR)/test-results for output from the tests"
	@grep -q "ERROR:\|FAIL:" $(BLDDIR)/test-results && exit 1 || true

test-setup:
	src/weedb/tests/setup_mysql.sh

test-setup-ci:
	MYSQL_NO_OPTS=1 src/weedb/tests/setup_mysql.sh

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


###############################################################################
## documentation targets

# Build the documentation:
build-docs: $(DOC_BUILT)

$(DOC_BUILT): $(shell find $(DOC_SRC) -type f)
	@rm -rf $(DOC_BUILT)
	@mkdir -p $(DOC_BUILT)
	@echo "Building documents"
	$(PYTHON) -m mkdocs --quiet build --site-dir=$(DOC_BUILT)

check-docs:
	weblint $(DOC_BUILT)/*.htm

# upload docs to the web site
upload-docs: $(DOC_BUILT)
	rsync -Orv --delete --exclude *~ --exclude "#*" $(DOC_BUILT)/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/docs/$(MMVERSION)


###############################################################################
## source targets

src-tarball: $(DSTDIR)/$(SRCPKG)

$(DSTDIR)/$(SRCPKG):
	mkdir -p $(BLDDIR)/weewx-$(VERSION)
	rsync -ar ./ $(BLDDIR)/weewx-$(VERSION) --exclude-from .gitignore --exclude .git --exclude .editorconfig --exclude .github --exclude .gitignore --delete
	mkdir -p $(DSTDIR)
	tar cfz $(DSTDIR)/$(SRCPKG) -C $(BLDDIR) weewx-$(VERSION)

# upload the source tarball to the web site
upload-src:
	scp $(DSTDIR)/$(SRCPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)


###############################################################################
## pypi targets

pypi-package $(DSTDIR)/$(WHEELSRC) $(DSTDIR)/$(WHEEL): pyproject.toml
	poetry build

# Upload wheel and src package to pypi.org
upload-pypi: $(DSTDIR)/$(WHEELSRC) $(DSTDIR)/$(WHEEL)
	poetry publish


###############################################################################
## debian targets

DEBREVISION=1
DEBVER=$(VERSION)-$(DEBREVISION)
# add a skeleton entry to deb changelog
debian-changelog:
	if [ "`grep '($(DEBVER))' pkg/debian/changelog`" = "" ]; then \
  pkg/mkchangelog.pl --action stub --format debian --release-version $(DEBVER) > pkg/debian/changelog.new; \
  cat pkg/debian/changelog >> pkg/debian/changelog.new; \
  mv pkg/debian/changelog.new pkg/debian/changelog; \
fi

# use dpkg-buildpackage to create the debian package
# -us -uc - skip gpg signature on .dsc, .buildinfo, and .changes
# the latest version in the debian changelog must match the packaging version
DEBARCH=all
DEBBLDDIR=$(BLDDIR)/weewx-$(VERSION)
DEBPKG=weewx_$(DEBVER)_$(DEBARCH).deb
ifneq ("$(SIGN)","1")
DPKG_OPT=-us -uc
endif
debian-package: deb-package-prep
	cp pkg/debian/control $(DEBBLDDIR)/debian/control
	rm -f $(DEBBLDDIR)/debian/files
	(cd $(DEBBLDDIR); dpkg-buildpackage $(DPKG_OPT))
	mkdir -p $(DSTDIR)
	mv $(BLDDIR)/$(DEBPKG) $(DSTDIR)/python3-$(DEBPKG)

deb-package-prep: $(DSTDIR)/$(SRCPKG)
	mkdir -p $(DEBBLDDIR)
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
	cp pkg/debian/source/format $(DEBBLDDIR)/debian/source
	cp pkg/debian/templates $(DEBBLDDIR)/debian
	cp pkg/debian/weewx.lintian-overrides $(DEBBLDDIR)/debian
	sed -e 's%WEEWX_VERSION%$(VERSION)%' \
  pkg/debian/rules > $(DEBBLDDIR)/debian/rules

# run lintian on the deb package
check-debian:
	lintian -Ivi $(DSTDIR)/python3-$(DEBPKG)

upload-debian:
	scp $(DSTDIR)/python3-$(DEBPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)


###############################################################################
## rpm targets

# specify the operating system release target (e.g., 7 for centos7)
OSREL=
# specify the operating system label (e.g., el, suse)
RPMOS=$(shell if [ -f /etc/SuSE-release -o -f /etc/SUSE-brand ]; then echo suse; elif [ -f /etc/redhat-release ]; then echo el; else echo os; fi)

RPMREVISION=1
RPMVER=$(VERSION)-$(RPMREVISION)
# add a skeleton entry to rpm changelog
rpm-changelog:
	if [ "`grep '\- $(RPMVER)' pkg/changelog.$(RPMOS)`" = "" ]; then \
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
	sed -e 's%WEEWX_VERSION%$(VERSION)%' \
            -e 's%RPMREVISION%$(RPMREVISION)%' \
            -e 's%OSREL%$(OSREL)%' \
            pkg/weewx.spec.in > $(RPMBLDDIR)/SPECS/weewx.spec
	cat pkg/changelog.$(RPMOS) >> $(RPMBLDDIR)/SPECS/weewx.spec
	cp $(DSTDIR)/$(SRCPKG) $(RPMBLDDIR)/SOURCES/weewx-$(VERSION).tar.gz
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

redhat-package: rpm-package-rh8 rpm-package-rh9

rpm-package-rh8:
	make rpm-package RPMOS=el OSREL=8

rpm-package-rh9:
	make rpm-package RPMOS=el OSREL=9

suse-changelog:
	make rpm-changelog RPMOS=suse

suse-package: rpm-package-suse15

rpm-package-suse15:
	make rpm-package RPMOS=suse OSREL=15

# run rpmlint on the rpm package
check-rpm:
	rpmlint -f pkg/rpmlint.$(RPMOS) $(DSTDIR)/$(RPMPKG)

check-redhat: check-rh8 check-rh9

check-rh8:
	make check-rpm RPMOS=el OSREL=8

check-rh9:
	make check-rpm RPMOS=el OSREL=9

check-suse:
	make check-rpm RPMOS=suse OSREL=15

upload-rpm:
	scp $(DSTDIR)/$(RPMPKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

upload-redhat: upload-rh8 upload-rh9

upload-rh8:
	make upload-rpm RPMOS=el OSREL=8

upload-rh9:
	make upload-rpm RPMOS=el OSREL=9

upload-suse:
	make upload-rpm RPMOS=suse OSREL=15

# shortcut to upload all packages from a single machine
DEB3_PKG=python3-weewx_$(DEBVER)_$(DEBARCH).deb
RHEL8_PKG=weewx-$(RPMVER).el8.$(RPMARCH).rpm
RHEL9_PKG=weewx-$(RPMVER).el9.$(RPMARCH).rpm
SUSE15_PKG=weewx-$(RPMVER).suse15.$(RPMARCH).rpm
upload-pkgs:
	scp $(DSTDIR)/$(SRCPKG) $(DSTDIR)/$(DEB3_PKG) $(DSTDIR)/$(RHEL8_PKG) $(DSTDIR)/$(RHEL9_PKG) $(DSTDIR)/$(SUSE15_PKG) $(USER)@$(WEEWX_COM):$(WEEWX_STAGING)

# move files from the upload directory to the release directory and set up the
# symlinks to them from the download root directory
DEVDIR=$(WEEWX_DOWNLOADS)/development_versions
RELDIR=$(WEEWX_DOWNLOADS)/released_versions
ARTIFACTS=$(DEB3_PKG) $(RHEL8_PKG) $(RHEL9_PKG) $(SUSE15_PKG) $(SRCPKG)
release:
	ssh $(USER)@$(WEEWX_COM) "for f in $(ARTIFACTS); do if [ -f $(DEVDIR)/\$$f ]; then mv $(DEVDIR)/\$$f $(RELDIR); fi; done"
	ssh $(USER)@$(WEEWX_COM) "rm -f $(WEEWX_DOWNLOADS)/weewx*"
	ssh $(USER)@$(WEEWX_COM) "if [ -f $(RELDIR)/$(SRCPKG) ]; then ln -s released_versions/$(SRCPKG) $(WEEWX_DOWNLOADS); fi"
	ssh $(USER)@$(WEEWX_COM) "chmod 664 $(WEEWX_DOWNLOADS)/released_versions/weewx?$(VERSION)*"


###############################################################################
## repository management targets

# update the repository html index files, without touching the contents of the
# repositories.  this is rarely necessary, since the index files are included
# in the pull/push cycle of repository maintenance.  it is needed when the
# operating systems make changes that are not backward compatible, for example
# when debian deprecated the use of apt-key.
upload-repo-index:
	scp pkg/index-apt.html $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly/public/index.html
	scp pkg/index-yum.html $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/yum/index.html
	scp pkg/index-suse.html $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/suse/index.html

# 'apt-repo' is only used when creating a new apt repository from scratch
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
	rsync -Oarvz --delete $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly/ ~/.aptly

# add the latest version to the local apt repo using aptly
update-apt-repo:
	aptly repo add python3-weewx $(DSTDIR)/python3-$(DEBPKG)
	aptly snapshot create python3-weewx-$(DEBVER) from repo python3-weewx
	aptly publish drop buster python3
	aptly publish -architectures=all snapshot python3-weewx-$(DEBVER) python3
#	aptly publish switch buster python3 python3-weewx-$(DEBVER)

# publish apt repo changes to the public weewx apt repo
push-apt-repo:
	find ~/.aptly -type f -exec chmod 664 {} \;
	find ~/.aptly -type d -exec chmod 2775 {} \;
	rsync -Ortlvz --delete ~/.aptly/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/aptly-test

# copy the testing repository onto the production repository
release-apt-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz --delete /var/www/html/aptly-test/ /var/www/html/aptly"

# 'yum-repo' is only used when creating a new yum repository from scratch
# the index.html is not part of an official rpm repository.  it is included
# to make the repository self-documenting.
YUM_REPO=~/.yum/weewx
yum-repo:
	mkdir -p $(YUM_REPO)/{el7,el8,el9}/RPMS
	cp -p pkg/index-yum.html ~/.yum/index.html
	cp -p pkg/weewx-el.repo ~/.yum/weewx.repo
	cp -p pkg/weewx-el7.repo ~/.yum
	cp -p pkg/weewx-el8.repo ~/.yum
	cp -p pkg/weewx-el9.repo ~/.yum

pull-yum-repo:
	mkdir -p $(YUM_REPO)
	rsync -Oarvz --delete $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/yum/ ~/.yum

update-yum-repo:
	mkdir -p $(YUM_REPO)/el8/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).el8.$(RPMARCH).rpm $(YUM_REPO)/el8/RPMS
	createrepo $(YUM_REPO)/el8
	mkdir -p $(YUM_REPO)/el9/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).el9.$(RPMARCH).rpm $(YUM_REPO)/el9/RPMS
	createrepo $(YUM_REPO)/el9
ifeq ("$(SIGN)","1")
	for os in el8 el9; do \
  gpg --export --armor > $(YUM_REPO)/$$os/repodata/repomd.xml.key; \
  gpg -abs -o $(YUM_REPO)/$$os/repodata/repomd.xml.asc.new $(YUM_REPO)/$$os/repodata/repomd.xml; \
  mv $(YUM_REPO)/$$os/repodata/repomd.xml.asc.new $(YUM_REPO)/$$os/repodata/repomd.xml.asc; \
done
endif

push-yum-repo:
	find ~/.yum -type f -exec chmod 664 {} \;
	find ~/.yum -type d -exec chmod 2775 {} \;
	rsync -Ortlvz --delete ~/.yum/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/yum-test

# copy the testing repository onto the production repository
release-yum-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz --delete /var/www/html/yum-test/ /var/www/html/yum"

# 'suse-repo' is only used when creating a new suse repository from scratch
# the index.html is not part of an official rpm repository.  it is included
# to make the repository self-documenting.
SUSE_REPO=~/.suse/weewx
suse-repo:
	mkdir -p $(SUSE_REPO)/{suse12,suse15}/RPMS
	cp -p pkg/index-suse.html ~/.suse/index.html
	cp -p pkg/weewx-suse.repo ~/.suse/weewx.repo
	cp -p pkg/weewx-suse12.repo ~/.suse
	cp -p pkg/weewx-suse15.repo ~/.suse

pull-suse-repo:
	mkdir -p $(SUSE_REPO)
	rsync -Oarvz --delete $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/suse/ ~/.suse

update-suse-repo:
	mkdir -p $(SUSE_REPO)/suse15/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).suse15.$(RPMARCH).rpm $(SUSE_REPO)/suse15/RPMS
	createrepo $(SUSE_REPO)/suse15
ifeq ("$(SIGN)","1")
	gpg --export --armor > $(SUSE_REPO)/suse15/repodata/repomd.xml.key
	gpg -abs -o $(SUSE_REPO)/suse15/repodata/repomd.xml.asc $(SUSE_REPO)/suse15/repodata/repomd.xml
	mv $(SUSE_REPO)/suse15/repodata/repomd.xml.asc.new $(SUSE_REPO)/suse15/repodata/repomd.xml.asc
endif

push-suse-repo:
	find ~/.suse -type f -exec chmod 664 {} \;
	find ~/.suse -type d -exec chmod 2775 {} \;
	rsync -Ortlvz --delete ~/.suse/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/suse-test

# copy the testing repository onto the production repository
release-suse-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz --delete /var/www/html/suse-test/ /var/www/html/suse"

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
	cloc --force-lang="HTML",tmpl --force-lang="INI",conf --force-lang="INI",inc src docs_src
