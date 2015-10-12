VERSION := $(shell python setup.py --version)

all: install

tmpcleaner.tar.gz: clean
	$(eval TMPDIR := $(shell mktemp -d))
	# Populate the spec file with correct version from setup.py
	tar czf "$(TMPDIR)/tmpcleaner.tar.gz" ../tmpcleaner
	mv "$(TMPDIR)/tmpcleaner.tar.gz" tmpcleaner.tar.gz
	rmdir "$(TMPDIR)"

build install:
	python setup.py $@

test:
	PYTHONPATH=${PYTHONPATH}:/build/rpm/BUILDROOT/tmpcleaner-${VERSION}-1.el6.x86_64$(rpm --eval '%{python_sitelib}') python setup.py $@

rpm: tmpcleaner.tar.gz
	# Prepare directories and source for rpmbuild
	mkdir -p build/rpm/SOURCES
	cp tmpcleaner.tar.gz build/rpm/SOURCES/
	mkdir -p build/rpm/SPECS
	cp tmpcleaner.spec build/rpm/SPECS/
	# Build RPM
	rpmbuild --define "_topdir $(CURDIR)/build/rpm" -ba build/rpm/SPECS/tmpcleaner.spec

sources: tmpcleaner.tar.gz

version:
	# Use for easier version bumping.
	# Helps keeping version consistent both in setup.py and tmpcleaner.spec
	@echo "Current version: $(VERSION)"
	@read -p "Type new version: " newversion; \
	sed -i -e "s/    'version': .*/    'version': '$$newversion',/" setup.py; \
	sed -i -e "s,Version:	.*,Version:	$$newversion," tmpcleaner.spec

upload:
	# You need following in ~/.pypirc to be able to upload new build
	# Also you need to be a maintainer or owner of gdc-tmpcleaner package
	#
	#	[pypi]
	#	username: xyz
	#	password: foo
	#
	#	[server-login]
	#	username: xyz
	#	password: foo
	#
	@while [ -z "$$CONTINUE" ]; do \
		read -r -p "Are you sure you want to upload version $(VERSION) to Pypi? [y/N] " CONTINUE; \
	done ; \
	if [ "$$CONTINUE" != "y" ]; then \
		echo "Exiting." ; exit 1 ; \
	fi

	python setup.py sdist upload

tag:
	git tag "v$(VERSION)"

release: tag upload
	$(info == Tagged and uploaded new version, do not forget to push new release tag and draft release on Github)

clean:
	rm -f tmpcleaner.tar.gz
	rm -rf tmpcleaner.egg-info
	rm -rf build
	rm -rf dist
