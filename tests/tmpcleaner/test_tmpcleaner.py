#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2014, GoodData(R) Corporation. All rights reserved

import unittest
import posix
import tempfile
import os
import stat
import gdctmpcleaner

class TestTmpcleaner(unittest.TestCase):
    def setUp(self):
        """
        Prepare testing directory structure
        """
        self.temp = tempfile.mkdtemp()
        for i in range(1, 20):
            os.mkdir('%s/%s' % (self.temp, i))
            for f in range(1, 5):
                with open('%s/%s/%s' % (self.temp, i, f), 'w') as fh:
                    fh.write(str(f))

    def tearDown(self):
        """
        Cleanup testing directory structure
        """
        for root, dirs, files in os.walk(self.temp, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))

            for d in dirs:
                os.rmdir(os.path.join(root, d))

    def test_file(self):
        """
        Test tmpcleaner.File
        """
        file_object = gdctmpcleaner.File(self.temp)

        self.assert_(isinstance(file_object.stat, posix.stat_result),
                     "Stat is not instance of posix.stat_result")
        self.assert_(isinstance(file_object.directory, bool),
            "File.directory should be boolean, not %s" %
                     type(file_object.directory))

        # Removing of non-empty directory should fail
        self.assertRaises(OSError, file_object.remove)

        # atime/mtime/ctime should be float
        for time in (file_object.atime, file_object.mtime, file_object.ctime):
            self.assert_(isinstance(time, float),
                "Returned atime/mtime/ctime should be float, not %s" % type(time))

        # Opening unsupported file type should raise UnsupportedFileType exception
        self.assertRaises(gdctmpcleaner.UnsupportedFileType,
                          gdctmpcleaner.File, '/dev/null')

    def test_definition_match_path(self):
        """
        Test tmpcleaner.Definition
        """
        ## Test path match
        path_match = '.*%s.*' % self.temp
        path_exclude = '.*%s/1/.*' % self.temp
        definition = gdctmpcleaner.Definition(
            name='test', pathMatch=path_match, pathExclude=path_exclude)

        file_temp = gdctmpcleaner.File(self.temp)

        # This should match
        self.assert_(definition.match_path(file_temp),
            "File %s haven't matched definition %s" % (self.temp, path_match))

        # Should be excluded
        self.assert_(definition.match_path(
            gdctmpcleaner.File('%s/1/3' % self.temp)) is False,
            "Excluded file %s haven't matched excluding definition %s" %
                     ('%s/1/3' % self.temp, path_exclude))

        # Time should be matched now, because it's empty
        self.assert_(definition.match_time(file_temp),
            "File %s haven't matched empty time definition" % self.temp)

    def test_definition_match_time(self):
        ## Test time match
        definition = gdctmpcleaner.Definition(mtime=5)
        file_temp = gdctmpcleaner.File(self.temp)
        # Modify mtime of tested file
        file_temp.mtime = 666

        # pathMatch is not defined, so it should always pass
        self.assert_(definition.match_path(file_temp),
            "File %s haven't matched empty definition" % self.temp)

        # time should match, because file is older than 5 hours
        self.assert_(definition.match_time(file_temp),
            "File %s haven't matched mtime" % self.temp)

        # following file isn't older than 5 hours, shouldn't match time
        self.assert_(definition.match_time(
            gdctmpcleaner.File('%s/1/3' % self.temp)) is False,
            "File %s matched mtime, but it shouldn't" % self.temp)


class TestE2E(unittest.TestCase):
    def setUp(self):
        """
        Prepare testing directory structure
        """

        config = '''---
pidfile: 'tmpcleaner-execution-log.pid'
path: '%s'

definitions:
    -
        name: 'test-def'
        pathMatch: '%s/.*'
        mtime: 1

'''
        self.temp = tempfile.mkdtemp()
        for i in range(1, 20):
            os.mkdir('%s/%s' % (self.temp, i))
            for f in range(1, 5):
                with open('%s/%s/%s' % (self.temp, i, f), 'w') as fh:
                    fh.write(str(f))

        self.config = tempfile.mktemp()
        parent, _ = os.path.split(self.temp)
        with open(self.config, 'a') as fh:
            fh.write(config % (parent, self.temp))

    def tearDown(self):
        """
        Cleanup testing directory structure
        """
        for root, dirs, files in os.walk(self.temp, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))

            for d in dirs:
                os.rmdir(os.path.join(root, d))

        os.unlink(self.config)

    def _age(self, path, days):
        """
        Change file(dir)'s mtime to past
        """
        st = os.stat(path)
        atime = st[stat.ST_ATIME]
        mtime = st[stat.ST_MTIME]
        new_mtime = mtime - 24*3600*days
        os.utime(path, (atime, new_mtime))

    def test_old_dir(self):
        cleaner = gdctmpcleaner.TmpCleaner(self.config)
        self._age(os.path.join(self.temp, '1'), 2)
        self._age(os.path.join(self.temp, '1', '1'), 2)
        cleaner.run()

        self.assertTrue(os.path.exists(os.path.join(self.temp, '1')))
        self.assertTrue(os.path.exists(os.path.join(self.temp, '1', '2')))
        self.assertTrue(os.path.exists(os.path.join(self.temp, '2')))

        self.assertFalse(os.path.exists(os.path.join(self.temp, '1', '1')))

class TestEscapeRoot(unittest.TestCase):
    def setUp(self):
        """
        Prepare testing directory structure
        """

        config = '''---
pidfile: 'tmpcleaner-execution-log2.pid'
path: '%s'

definitions:
    -
        name: 'test-def'
        pathMatch: '.*'
        mtime: 0

'''
        self.temp = tempfile.mkdtemp()
        for i in range(1, 20):
            os.mkdir('%s/%s' % (self.temp, i))
            for f in range(1, 5):
                with open('%s/%s/%s' % (self.temp, i, f), 'w') as fh:
                    fh.write(str(f))

        self.config = tempfile.mktemp()
        with open(self.config, 'a') as fh:
            fh.write(config % self.temp)

    def tearDown(self):
        """
        Cleanup testing directory structure
        """
        for root, dirs, files in os.walk(self.temp, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))

            for d in dirs:
                os.rmdir(os.path.join(root, d))

        os.unlink(self.config)

    def test_escape_root(self):
        cleaner = gdctmpcleaner.TmpCleaner(self.config)
        cleaner.run()

        self.assertFalse(os.path.exists(os.path.join(self.temp, '1')))
        self.assertFalse(os.path.exists(os.path.join(self.temp, '20')))

        self.assertTrue(os.path.exists(self.temp))

class TestStats(unittest.TestCase):
    def setUp(self):
        """
        Prepare testing directory structure
        """

        config = '''---
pidfile: 'tmpcleaner-execution-log3.pid'
path: '%s'

definitions:
    -
        name: 'test-def'
        pathMatch: '%s/.*'
        mtime: 1

'''
        self.temp = tempfile.mkdtemp()
        for i in range(1, 20):
            os.mkdir('%s/%s' % (self.temp, i))
            for f in range(1, 5):
                with open('%s/%s/%s' % (self.temp, i, f), 'w') as fh:
                    fh.write(str(f))
        os.mkdir('%s/20' % self.temp)

        self.config = tempfile.mktemp()
        with open(self.config, 'a') as fh:
            fh.write(config % (self.temp, self.temp))

    def tearDown(self):
        """
        Cleanup testing directory structure
        """
        for root, dirs, files in os.walk(self.temp, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))

            for d in dirs:
                os.rmdir(os.path.join(root, d))

        os.unlink(self.config)

    def _age(self, path, days):
        """
        Change file(dir)'s mtime to past
        """
        st = os.stat(path)
        atime = st[stat.ST_ATIME]
        mtime = st[stat.ST_MTIME]
        new_mtime = mtime - 24*3600*days
        os.utime(path, (atime, new_mtime))

    def _size(self, path, size):
        with open(path, 'w') as fh:
            fh.write('\0' * size)

    def test_stats(self):
        self._size(os.path.join(self.temp, '1', '1'), 1024*1024)
        self._size(os.path.join(self.temp, '5', '1'), 1024*1024)
        self._size(os.path.join(self.temp, '6', '1'), 1024*1024)
        self._size(os.path.join(self.temp, '7', '1'), 1024*1024)
        self._size(os.path.join(self.temp, '8', '1'), 1024*1024)
        self._size(os.path.join(self.temp, '9', '1'), 1024*1024)

        self._age(os.path.join(self.temp, '1', '1'), 2)
        self._age(os.path.join(self.temp, '1', '2'), 2)
        self._age(os.path.join(self.temp, '1', '3'), 2)
        self._age(os.path.join(self.temp, '1', '4'), 2)
        self._age(os.path.join(self.temp, '20'), 2)
        self._age(os.path.join(self.temp, '2', '1'), 2)
        self._age(os.path.join(self.temp, '3', '1'), 2)

        cleaner = gdctmpcleaner.TmpCleaner(self.config)
        cleaner.run()

        self.assertEqual(
            cleaner.summary['test-def']['removed']['files'], 6)
        self.assertEqual(
            cleaner.summary['test-def']['removed']['dirs'], 1)
        self.assertEqual(
            cleaner.summary['test-def']['existing']['files'], 70)
        self.assertEqual(
            cleaner.summary['test-def']['existing']['dirs'], 19)

        self.assertTrue(
            (cleaner.summary['test-def']['removed']['size'] - 1024*1024) <
            abs(1024))
        self.assertTrue(
            (cleaner.summary['test-def']['existing']['size'] - 5*1024*1024) <
            abs(1024))


if __name__ == '__main__':
    unittest.main()
