#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2014, GoodData(R) Corporation. All rights reserved

import unittest
import posix
import tempfile
import datetime
import os
import tmpcleaner

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
        file_object = tmpcleaner.File(self.temp)

        self.assert_(isinstance(file_object.stat, posix.stat_result), "Stat is not instance of posix.stat_result")
        self.assert_(isinstance(file_object.directory, bool),\
            "File.directory should be boolean, not %s" % type(file_object.directory))

        # Removing of non-empty directory should fail
        self.assertRaises(OSError, file_object.remove)

        # atime/mtime/ctime should be datetime objects
        for time in (file_object.atime, file_object.mtime, file_object.ctime):
            self.assert_(isinstance(time, datetime.datetime),\
                "Returned atime/mtime/ctime should be datetime objects, not %s" % type(time))

        # Opening unsupported file type should raise UnsupportedFileType exception
        self.assertRaises(tmpcleaner.UnsupportedFileType, tmpcleaner.File, '/dev/null')

    def test_definition_match_path(self):
        """
        Test tmpcleaner.Definition
        """
        ## Test path match
        path_match = '.*%s.*' % self.temp
        path_exclude = '.*%s/1/.*' % self.temp
        definition = tmpcleaner.Definition(name='test', pathMatch=path_match, pathExclude=path_exclude)

        file_temp = tmpcleaner.File(self.temp)

        # This should match
        self.assert_(definition.match_path(file_temp) == True,\
            "File %s haven't matched definition %s" % (self.temp, path_match))

        # Should be excluded
        self.assert_(definition.match_path(tmpcleaner.File('%s/1/3' % self.temp)) == False, \
            "Excluded file %s haven't matched excluding definition %s" % ('%s/1/3' % self.temp, path_exclude))

        # Time should be matched now, because it's empty
        self.assert_(definition.match_time(file_temp) == True,\
            "File %s haven't matched empty time definition" % self.temp)

    def test_definition_match_time(self):
        ## Test time match
        definition = tmpcleaner.Definition(mtime=5)
        file_temp = tmpcleaner.File(self.temp)
        # Modify mtime of tested file
        file_temp.mtime = datetime.datetime.fromtimestamp(666)

        # pathMatch is not defined, so it should always pass
        self.assert_(definition.match_path(file_temp) == True, \
            "File %s haven't matched empty definition" % self.temp)

        # time should match, because file is older than 5 hours
        self.assert_(definition.match_time(file_temp) == True, \
            "File %s haven't matched mtime" % self.temp)

        # following file isn't older than 5 hours, shouldn't match time
        self.assert_(definition.match_time(tmpcleaner.File('%s/1/3' % self.temp)) == False, \
            "File %s matched mtime, but it shouldn't" % self.temp)

if __name__ == '__main__':
    unittest.main()
