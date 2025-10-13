# -*- makefile -*-
# this makefile controls the build and packaging of weewx
# Copyright 2013-2025 Matthew Wall

# We default to *not* signing - this makes testing and development easier.
# If you are going to do an official release, then you must sign. Indicate this
# by specifying the identifier of the GPG key you want to use. To see your GPG
# key identifiers, invoke 'gpg --list-secret-keys'
GPG_KEYID?=

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

help-release: info
	@echo "options to stage and release include:"
	@echo ""
	@echo "     stage-all  upload packages and repos to staging"
	@echo "    upload-src  upload src package to staging"
	@echo " upload-debian  upload debian package to staging"
	@echo " upload-redhat  upload redhat package to staging"
	@echo "   upload-suse  upload suse package to staging"
	@echo ""
	@echo "   release-all  promote packages and repos to production"
	@echo "  release-pkgs  promote packages to production"
	@echo "  release-pypi  upload wheel and src package to pypi.org"
	@echo ""
	@echo " apt repository management"
	@echo "     pull-apt-repo  synchronize local repo to weewx.com"
	@echo "   update-apt-repo  update local repo using local package"
	@echo "     push-apt-repo  synchronize weewx.com testing to local repo"
	@echo "  release-apt-repo  move testing to production"
	@echo ""
	@echo " yum repository management"
	@echo "     pull-yum-repo  synchronize local repo to weewx.com"
	@echo "   update-yum-repo  update local repo using local package"
	@echo "     push-yum-repo  synchronize weewx.com testing to local repo"
	@echo "  release-yum-repo  move testing to production"
	@echo ""
	@echo " suse repository management"
	@echo "    pull-suse-repo  synchronize local repo to weewx.com"
	@echo "  update-suse-repo  update local repo using local package"
	@echo "    push-suse-repo  synchronize weewx.com testing to local repo"
	@echo " release-suse-repo  move testing to production"
	@echo ""



info:
	@echo "       VERSION: $(VERSION)"
	@echo "     MMVERSION: $(MMVERSION)"
	@echo "        PYTHON: $(PYTHON)"
	@echo "           CWD: $(CWD)"
	@echo "          USER: $(USER)"
	@echo "     GPG_KEYID: $(GPG_KEYID)"
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
## release management targets

# shortcuts to upload everything.  assumes that the assets have been staged
# to the local 'dist' directory.
stage-all: upload-src upload-pkgs push-apt-repo push-yum-repo push-suse-repo

# shortcut to release everything.  assumes that all of the assets have been
# staged to the development area on the distribution server.
release-all: release-pkgs release-apt-repo release-yum-repo release-suse-repo


###############################################################################
## documentation targets

# Build the documentation:
build-docs: $(DOC_BUILT)/index.html

$(DOC_BUILT)/index.html: $(shell find $(DOC_SRC) -type f)
	@rm -rf $(DOC_BUILT)
	@mkdir -p $(DOC_BUILT)
	@echo "Building documents"
	$(PYTHON) -m mkdocs --quiet build --site-dir=$(DOC_BUILT)

# upload docs to the web site
upload-docs: $(DOC_BUILT)/index.html
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
release-pypi upload-pypi: $(DSTDIR)/$(WHEELSRC) $(DSTDIR)/$(WHEEL)
	poetry publish


###############################################################################
## debian targets

DEBREVISION=1
DEBVER=$(VERSION)-$(DEBREVISION)
# add a skeleton entry to deb changelog
debian-changelog:
	if [ "`grep '($(DEBVER))' pkg/debian/changelog`" = "" ]; then \
  set --; \
  if [ -n "$(USER)" ]; then set -- "$$@" --user "$(USER)"; fi; \
  if [ -n "$(EMAIL)" ]; then set -- "$$@" --email "$(EMAIL)"; fi; \
  if [ "$(GPG_KEYID)" = "" ]; then set -- "$$@" --ignore-gpg; fi; \
  pkg/mkchangelog.pl --action stub --format debian --release-version $(DEBVER) > pkg/debian/changelog.new; \
  cat pkg/debian/changelog >> pkg/debian/changelog.new; \
  mv pkg/debian/changelog.new pkg/debian/changelog; \
fi

# use dpkg-buildpackage to create the debian package
# -us -ui -uc - skip gpg signature on .dsc, .buildinfo, and .changes
# the latest version in the debian changelog must match the packaging version
DEBARCH=all
DEBBLDDIR=$(BLDDIR)/weewx-$(VERSION)
DEBPKG=weewx_$(DEBVER)_$(DEBARCH).deb
ifeq ("$(GPG_KEYID)","")
DPKG_OPT=--no-sign
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
	chmod 755 $(DEBBLDDIR)/debian/rules

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
  set --; \
  if [ -n "$(USER)" ]; then set -- "$$@" --user "$(USER)"; fi; \
  if [ -n "$(EMAIL)" ]; then set -- "$$@" --email "$(EMAIL)"; fi; \
  if [ "$(GPG_KEYID)" = "" ]; then set -- "$$@" --ignore-gpg; fi; \
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
ifneq ("$(GPG_KEYID)","")
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
release-pkgs:
	ssh $(USER)@$(WEEWX_COM) "for f in $(ARTIFACTS); do if [ -f $(DEVDIR)/\$$f ]; then mv $(DEVDIR)/\$$f $(RELDIR); fi; done"
	ssh $(USER)@$(WEEWX_COM) "rm -f $(WEEWX_DOWNLOADS)/weewx*"
	ssh $(USER)@$(WEEWX_COM) "if [ -f $(RELDIR)/$(SRCPKG) ]; then ln -s released_versions/$(SRCPKG) $(WEEWX_DOWNLOADS); fi"
	ssh $(USER)@$(WEEWX_COM) "chmod 664 $(WEEWX_DOWNLOADS)/released_versions/weewx?$(VERSION)*"


###############################################################################
## repository management targets

REPO_DIR=/var/tmp/repo
REPO_NAME=repo
pull-repo:
	mkdir -p $(REPO_DIR)
	rsync -Ortlogvz --delete $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/$(REPO_NAME)/ $(REPO_DIR)

push-repo:
	find $(REPO_DIR) -type f -exec chmod 664 {} \;
	find $(REPO_DIR) -type d -exec chmod 2775 {} \;
	rsync -Ortlvz --delete $(REPO_DIR)/ $(USER)@$(WEEWX_COM):$(WEEWX_HTMLDIR)/$(REPO_NAME)-test

release-repo:
	ssh $(USER)@$(WEEWX_COM) "rsync -Ologrvz --delete /var/www/html/$(REPO_NAME)-test/ /var/www/html/$(REPO_NAME)"

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
APTLY_DIR=/var/tmp/repo-apt
apt-repo:
	aptly -config=pkg/aptly.conf repo create -distribution=squeeze -component=main -architectures=all python2-weewx
	aptly -config=pkg/aptly.conf repo create -distribution=buster -component=main -architectures=all python3-weewx
	mkdir -p $(APTLY_DIR)/public
	cp -p pkg/index-apt.html $(APTLY_DIR)/public/index.html
	cp -p pkg/weewx-python2.list $(APTLY_DIR)/public
	cp -p pkg/weewx-python3.list $(APTLY_DIR)/public
# this is for backward-compatibility when there was not python2/3 distinction
	cp -p pkg/weewx-python2.list $(APTLY_DIR)/public/weewx.list
# these are for backward-compatibility for users that do not have python2 or
# python3 in the paths in their .list file - default to python2
	ln -s python2/dists $(APTLY_DIR)/public
	ln -s python2/pool $(APTLY_DIR)/public

# make local copy of the published apt repository
pull-apt-repo:
	make pull-repo REPO_NAME=aptly REPO_DIR=$(APTLY_DIR)

# add the latest version to the local apt repo using aptly
update-apt-repo:
	aptly -config=pkg/aptly.conf repo add python3-weewx $(DSTDIR)/python3-$(DEBPKG)
	aptly -config=pkg/aptly.conf snapshot create python3-weewx-$(DEBVER) from repo python3-weewx
	aptly -config=pkg/aptly.conf publish drop buster python3
	aptly -config=pkg/aptly.conf publish -architectures=all snapshot python3-weewx-$(DEBVER) python3
#	aptly -config=pkg/aptly.conf publish switch buster python3 python3-weewx-$(DEBVER)

# publish apt repo changes to the public weewx apt repo
push-apt-repo:
	make push-repo REPO_NAME=aptly REPO_DIR=$(APTLY_DIR)

# copy the testing repository onto the production repository
release-apt-repo:
	make release-repo REPO_NAME=aptly REPO_DIR=$(APTLY_DIR)

# 'yum-repo' is only used when creating a new yum repository from scratch
# the index.html is not part of an official rpm repository.  it is included
# to make the repository self-documenting.
YUM_DIR=/var/tmp/repo-yum
YUM_REPO=$(YUM_DIR)/weewx
yum-repo:
	mkdir -p $(YUM_REPO)/{el7,el8,el9}/RPMS
	cp -p pkg/index-yum.html $(YUM_DIR)/index.html
	cp -p pkg/weewx-el.repo $(YUM_DIR)/weewx.repo
	cp -p pkg/weewx-el7.repo $(YUM_DIR)
	cp -p pkg/weewx-el8.repo $(YUM_DIR)
	cp -p pkg/weewx-el9.repo $(YUM_DIR)

pull-yum-repo:
	make pull-repo REPO_NAME=yum REPO_DIR=$(YUM_DIR)

update-yum-repo:
	mkdir -p $(YUM_REPO)/el8/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).el8.$(RPMARCH).rpm $(YUM_REPO)/el8/RPMS
	createrepo $(YUM_REPO)/el8
	mkdir -p $(YUM_REPO)/el9/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).el9.$(RPMARCH).rpm $(YUM_REPO)/el9/RPMS
	createrepo $(YUM_REPO)/el9
ifneq ("$(GPG_KEYID)","")
	for os in el8 el9; do \
  gpg --export --armor > $(YUM_REPO)/$$os/repodata/repomd.xml.key; \
  gpg -abs -o $(YUM_REPO)/$$os/repodata/repomd.xml.asc.new $(YUM_REPO)/$$os/repodata/repomd.xml; \
  mv $(YUM_REPO)/$$os/repodata/repomd.xml.asc.new $(YUM_REPO)/$$os/repodata/repomd.xml.asc; \
done
endif

push-yum-repo:
	make push-repo REPO_NAME=yum REPO_DIR=$(YUM_DIR)

release-yum-repo:
	make release-repo REPO_NAME=yum REPO_DIR=$(YUM_DIR)

# 'suse-repo' is only used when creating a new suse repository from scratch
# the index.html is not part of an official rpm repository.  it is included
# to make the repository self-documenting.
SUSE_DIR=/var/tmp/repo-suse
SUSE_REPO=$(SUSE_DIR)/weewx
suse-repo:
	mkdir -p $(SUSE_REPO)/{suse12,suse15}/RPMS
	cp -p pkg/index-suse.html $(SUSE_DIR)/index.html
	cp -p pkg/weewx-suse.repo $(SUSE_DIR)/weewx.repo
	cp -p pkg/weewx-suse12.repo $(SUSE_DIR)
	cp -p pkg/weewx-suse15.repo $(SUSE_DIR)

pull-suse-repo:
	make pull-repo REPO_NAME=suse REPO_DIR=$(SUSE_DIR)

update-suse-repo:
	mkdir -p $(SUSE_REPO)/suse15/RPMS
	cp -p $(DSTDIR)/weewx-$(RPMVER).suse15.$(RPMARCH).rpm $(SUSE_REPO)/suse15/RPMS
	createrepo $(SUSE_REPO)/suse15
ifneq ("$(GPG_KEYID)","")
	gpg --export --armor > $(SUSE_REPO)/suse15/repodata/repomd.xml.key
	gpg -abs -o $(SUSE_REPO)/suse15/repodata/repomd.xml.asc.new $(SUSE_REPO)/suse15/repodata/repomd.xml
	mv $(SUSE_REPO)/suse15/repodata/repomd.xml.asc.new $(SUSE_REPO)/suse15/repodata/repomd.xml.asc
endif

push-suse-repo:
	make push-repo REPO_NAME=suse REPO_DIR=$(SUSE_DIR)

release-suse-repo:
	make release-repo REPO_NAME=suse REPO_DIR=$(SUSE_DIR)


###############################################################################
## miscellaneous

# run perlcritic to ensure clean perl code.  put these in ~/.perlcriticrc:
# [-CodeLayout::RequireTidyCode]
# [-Modules::ProhibitExcessMainComplexity]
# [-Modules::RequireVersionVar]
critic:
	perlcritic -1 --verbose 8 pkg/mkchangelog.pl

code-summary:
	cloc --force-lang="HTML",tmpl --force-lang="INI",conf --force-lang="INI",inc src docs_src


###############################################################################
## virtual machine targets

# use the following targets to build the platform packages in virtual machines
# using vagrant.  this requires that vagrant and a suitable virtual machine
# framework such as virtualbox is installed.
#
# we would like to use a shared directory for the repo, but that does not work.
# the guest os fails with 'operation not permitted' when it tries to manipulate
# files/links in the shared directory.
#
# we would like to do all of the builds in the guests, then do the signing in
# the host.  unfortunately its not that easy.  debian packages are typically
# not signed (unless you distribute them individually), but debian repos are.
# redhat and suse want you to sign the packages as well as the repository.
# since only rpmsign can be used to sign redhat/suse artifacts, we must do the
# signing in the guests.  so we have to get the gpg credentials into the guest
# with export/import, and that requires a passphrase, so we stash it in a file.

DEB_VM=debian12
RHEL_VM=rocky8
SUSE_VM=suse15

VM_GUEST=undefined
VM_URL=vagrant@default:/home/vagrant
VM_DIR=build/vm-$(VM_GUEST)
VM_CFG=vagrant/Vagrantfile-$(VM_GUEST)-dev
VM_TGT=weewx-package
VM_PKG=weewx.pkg
vagrant-setup:
	mkdir -p $(VM_DIR)
	cp $(VM_CFG) $(VM_DIR)/Vagrantfile
	(cd $(VM_DIR); vagrant up; vagrant ssh-config > ssh-config)

# export gpg keys then import, in case the guest gpg is way behind the host
vagrant-sync-gpg:
ifneq ("$(GPG_KEYID)","")
	@if [ -d "$(HOME)/.gnupg" ]; then \
  if [ -f "$(HOME)/.gnupg/passphrase" ]; then \
    gpg -a --export $(GPG_KEYID) > /tmp/gpg-pubkeys.asc; \
    gpg -a --pinentry-mode=loopback --passphrase-file $(HOME)/.gnupg/passphrase --export-secret-key $(GPG_KEYID) > /tmp/gpg-prikeys.asc; \
    gpg_name=`gpg --list-secret-keys | grep uid | awk '{$$1=$$2=""; print $$0}'`; sed "s/GPG_NAME/$${gpg_name}/" vagrant/rpmmacros > /tmp/gpg-macros; \
    ssh -F $(VM_DIR)/ssh-config vagrant@default "mkdir -p .gnupg; chmod 700 .gnupg"; \
    scp -F $(VM_DIR)/ssh-config vagrant/gpg.conf $(VM_URL)/.gnupg; \
    scp -F $(VM_DIR)/ssh-config /tmp/gpg-macros $(VM_URL)/.rpmmacros; \
    scp -F $(VM_DIR)/ssh-config $(HOME)/.gnupg/passphrase $(VM_URL)/.gnupg; \
    scp -F $(VM_DIR)/ssh-config /tmp/gpg-pubkeys.asc $(VM_URL)/.gnupg; \
    scp -F $(VM_DIR)/ssh-config /tmp/gpg-prikeys.asc $(VM_URL)/.gnupg; \
    ssh -F $(VM_DIR)/ssh-config vagrant@default "gpg --import .gnupg/gpg-pubkeys.asc"; \
    ssh -F $(VM_DIR)/ssh-config vagrant@default "gpg --import .gnupg/gpg-prikeys.asc"; \
    rm -f /tmp/gpg-pubkeys.asc /tmp/gpg-prikeys.asc /tmp/gpg-macros; \
  else \
    echo "to sign pkgs and repos, you must save passphrase in ~/.gnupg/passphrase"; \
  fi \
else \
  echo "signing requested, but no key info found at $(HOME)/.gnupg"; \
fi
endif

vagrant-sync-src:
	rsync -ar -e "ssh -F $(VM_DIR)/ssh-config" --exclude build --exclude dist --exclude vm ./ $(VM_URL)/weewx

vagrant-build:
	ssh -F $(VM_DIR)/ssh-config vagrant@default "cd weewx; make $(VM_TGT) GPG_KEYID=$(GPG_KEYID)"

vagrant-pull-repo:
	rsync -ar -e "ssh -F $(VM_DIR)/ssh-config" vagrant@default:$(REPO_DIR)/ $(REPO_DIR)

vagrant-push-repo:
	rsync -ar -e "ssh -F $(VM_DIR)/ssh-config" $(REPO_DIR)/ vagrant@default:$(REPO_DIR)

vagrant-pull-pkg:
	mkdir -p $(DSTDIR)
	scp -F $(VM_DIR)/ssh-config "$(VM_URL)/weewx/dist/$(VM_PKG)" $(DSTDIR)

vagrant-push-pkg:
	ssh -F $(VM_DIR)/ssh-config vagrant@default "mkdir -p /home/vagrant/weewx/dist"
	scp -F $(VM_DIR)/ssh-config $(DSTDIR)/$(VM_PKG) "$(VM_URL)/weewx/dist"

vagrant-update-repo:
	ssh -F $(VM_DIR)/ssh-config vagrant@default "cd weewx; make $(VM_REPO_TGT) GPG_KEYID=$(GPG_KEYID)"

vagrant-teardown:
	(cd $(VM_DIR); vagrant destroy -f)

debian-package-via-vagrant:
	make vagrant-setup VM_GUEST=$(DEB_VM)
	make vagrant-sync-gpg VM_GUEST=$(DEB_VM)
	make vagrant-sync-src VM_GUEST=$(DEB_VM)
	make vagrant-build VM_GUEST=$(DEB_VM) VM_TGT=debian-package GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-pkg VM_GUEST=$(DEB_VM) VM_PKG=$(DEB3_PKG)
	make vagrant-teardown VM_GUEST=$(DEB_VM)

redhat-package-via-vagrant:
	make vagrant-setup VM_GUEST=$(RHEL_VM)
	make vagrant-sync-gpg VM_GUEST=$(RHEL_VM)
	make vagrant-sync-src VM_GUEST=$(RHEL_VM)
	make vagrant-build VM_GUEST=$(RHEL_VM) VM_TGT=redhat-package GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-pkg VM_GUEST=$(RHEL_VM) VM_PKG=$(RHEL8_PKG)
	make vagrant-pull-pkg VM_GUEST=$(RHEL_VM) VM_PKG=$(RHEL9_PKG)
	make vagrant-teardown VM_GUEST=$(RHEL_VM)

suse-package-via-vagrant:
	make vagrant-setup VM_GUEST=$(SUSE_VM)
	make vagrant-sync-gpg VM_GUEST=$(SUSE_VM)
	make vagrant-sync-src VM_GUEST=$(SUSE_VM)
	make vagrant-build VM_GUEST=$(SUSE_VM) VM_TGT=suse-package GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-pkg VM_GUEST=$(SUSE_VM) VM_PKG=$(SUSE15_PKG)
	make vagrant-teardown VM_GUEST=$(SUSE_VM)

# The package repositories must be updated using tools on their respective
# operating systems.  So for each repository, we first pull the canonical repo
# from weewx.con to the host, then we do the update on the guest operating
# system, then we sync those changes to the host, then we push the result to
# the testing repository on weewx.com.  This requires that the repository
# directory is hosted on the host and visible to the guest, a configuration
# option that is specified in the vagrant file for each guest.

apt-repo-via-vagrant:
	make pull-repo REPO_NAME=aptly REPO_DIR=$(APTLY_DIR)
	make vagrant-setup VM_GUEST=$(DEB_VM)
	make vagrant-sync-gpg VM_GUEST=$(DEB_VM)
	make vagrant-sync-src VM_GUEST=$(DEB_VM)
	make vagrant-push-pkg VM_GUEST=$(DEB_VM) VM_PKG=$(DEB3_PKG)
	make vagrant-push-repo VM_GUEST=$(DEB_VM) REPO_DIR=$(APTLY_DIR)
	make vagrant-update-repo VM_GUEST=$(DEB_VM) VM_REPO_TGT=update-apt-repo GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-repo VM_GUEST=$(DEB_VM) REPO_DIR=$(APTLY_DIR)
	make vagrant-teardown VM_GUEST=$(DEB_VM)

yum-repo-via-vagrant:
	make pull-repo REPO_NAME=yum REPO_DIR=$(YUM_DIR)
	make vagrant-setup VM_GUEST=$(RHEL_VM)
	make vagrant-sync-gpg VM_GUEST=$(RHEL_VM)
	make vagrant-sync-src VM_GUEST=$(RHEL_VM)
	make vagrant-push-pkg VM_GUEST=$(RHEL_VM) VM_PKG=$(RHEL8_PKG)
	make vagrant-push-pkg VM_GUEST=$(RHEL_VM) VM_PKG=$(RHEL9_PKG)
	make vagrant-push-repo VM_GUEST=$(RHEL_VM) REPO_DIR=$(YUM_DIR)
	make vagrant-update-repo VM_GUEST=$(RHEL_VM) VM_REPO_TGT=update-yum-repo GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-repo VM_GUEST=$(RHEL_VM) REPO_DIR=$(YUM_DIR)
	make vagrant-teardown VM_GUEST=$(RHEL_VM)

suse-repo-via-vagrant:
	make pull-repo REPO_NAME=suse REPO_DIR=$(SUSE_DIR)
	make vagrant-setup VM_GUEST=$(SUSE_VM)
	make vagrant-sync-gpg VM_GUEST=$(SUSE_VM)
	make vagrant-sync-src VM_GUEST=$(SUSE_VM)
	make vagrant-push-pkg VM_GUEST=$(SUSE_VM) VM_PKG=$(SUSE15_PKG)
	make vagrant-push-repo VM_GUEST=$(SUSE_VM) REPO_DIR=$(SUSE_DIR)
	make vagrant-update-repo VM_GUEST=$(SUSE_VM) VM_REPO_TGT=update-suse-repo GPG_KEYID=$(GPG_KEYID)
	make vagrant-pull-repo VM_GUEST=$(SUSE_VM) REPO_DIR=$(SUSE_DIR)
	make vagrant-teardown VM_GUEST=$(SUSE_VM)
