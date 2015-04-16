#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2014, GoodData(R) Corporation. All rights reserved

import sys
import os
from setuptools import setup
from setuptools.command.test import test as TestCommand

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['--junitxml=%s/tests.xml' % os.getcwd()]
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

# Get current branch
branch = os.getenv('GIT_BRANCH')
if not branch:
    branch = os.popen('git branch|grep -v "no branch"|grep \*|sed s,\*\ ,,g').read().rstrip()

    if not branch:
        branch = 'master'
else:
    branch = branch.replace('origin/', '')

# Get git revision hash
revision = os.popen('git rev-parse --short HEAD').read().rstrip()

if not revision:
    revision = '0'

# Get build number
build = os.getenv('BUILD_NUMBER')
if not build:
    build = '1'

# Parameters for build
params = {
    'name': 'tmpcleaner',
    'version': '1.0',
    'packages': [
        'tmpcleaner',
        'tmpcleaner.logger'
        ],
    'scripts': [
        'bin/tmpcleaner.py',
        ],
    'url': 'https://github.com/gooddata/tmpcleaner',
    'download_url': 'https://github.com/gooddata/tmpcleaner',
    'license': 'BSD',
    'author': 'GoodData Corporation',
    'author_email': 'python@gooddata.com',
    'maintainer': 'Filip Pytloun',
    'maintainer_email': 'filip@pytloun.cz',
    'description': 'Smart Temp Cleaner',
    'long_description': '''Tmpcleaner is simply advanced temp cleaner with statistical capabilities.
It passes given structure only once, groups directories/files by given definition, applies different cleanup rules by each group and print final statistics.''',
    'tests_require': ['pytest'],
    'cmdclass': {'test': PyTest},
    'requires': ['yaml', 'argparse'],
    'classifiers': [
        'Development Status:: 5 - Production/Stable',
        'Environment:: Console',
        'Intended Audience:: Developers',
        'Intended Audience:: System Administrators',
        'License:: OSI Approved:: BSD License',
        'Natural Language:: English',
        'Operating System:: POSIX',
        'Programming Language:: Python',
        'Programming Language:: Python:: Implementation:: CPython',
        'Topic:: System:: Monitoring',
    ],
    'platforms': ['POSIX'],
}

try:
    action = sys.argv[1]
except IndexError:
    action = None

if action == 'clean':
    # Remove MANIFEST file
    print "Cleaning MANIFEST.."
    try:
        os.unlink('MANIFEST')
    except OSError as e:
        if e.errno == 2:
            pass
        else:
            raise

    # Remove dist and build directories
    for dir in ['dist', 'build']:
        print "Cleaning %s.." % dir
        for root, dirs, files in os.walk(dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        try:
            os.rmdir(dir)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise
elif action == 'bdist_rpm':
    # Set release number
    sys.argv.append('--release=1.%s.%s' % (build, revision))
    # Require same version of gdc-python-common package
    sys.argv.append('--requires=PyYAML python-argparse python-dateutil')
    setup(**params)
else:
    setup(**params)
