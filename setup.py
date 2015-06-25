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

# Parameters for build
params = {
    'name': 'tmpcleaner',
    'version': '1.0.4',
    'packages': [
        'gdctmpcleaner',
        'gdctmpcleaner.logger'
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

setup(**params)
