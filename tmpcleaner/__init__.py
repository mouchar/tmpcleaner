# -*- coding: utf-8 -*-
# Copyright (C) 2007-2014, GoodData(R) Corporation. All rights reserved

"""
Simple temp cleaner with support for statistics and multiple filter definitions
"""

import os
import errno
import atexit
import stat
import posix

from itertools import count

import yaml
import re
from datetime import datetime, timedelta

import logging
lg = logging.getLogger(__name__)


class TmpCleaner(object):
    """
    Cleaner class
    """
    def __init__(self, config, dry=False):
        """
        Load config
        Initialize logging if it isn't initialized

        :param config: config file to use
        :param dry: dry-run only (default False)
        """
        self.dry = dry
        self.definitions = []
        self.files = []

        self.time_run = timedelta(seconds=0)

        if self.dry:
            lg.info("Running in dry-run mode")

        if not os.path.isfile(config):
            raise NoConfigFile('Config file %s not found' % config)

        with open(config, 'r') as fh:
            self.config = yaml.load(fh.read())
            lg.debug("Loaded config file %s" % config)

        # Setup definitions
        if self.config.has_key('definitions'):
            for definition in self.config['definitions']:
                self.definitions.append(Definition(**definition))
        else:
            raise InvalidConfiguration('Config section definitions not present')

        # Setup summary structure
        self.summary = {
            None: {
                'failed': {'dirs': 0, 'files': 0},
                'removed': {'dirs': 0, 'files': 0},
                'existing': {'dirs': 0, 'files': 0},
            }
        }

        for definition in self.definitions:
            self.summary[definition.name] = {
                'failed': {'dirs': 0, 'files': 0},
                'removed': {'dirs': 0, 'files': 0},
                'existing': {'dirs': 0, 'files': 0},
            }

        # Compile regexp for excluded paths
        if self.config.has_key('pathIgnore') and self.config['pathIgnore']:
            self.path_ignore = re.compile(self.config['pathIgnore'])
        else:
            self.path_ignore = None

        # Check and write pidfile
        if self.config['pidfile'] and not self.dry:
            if os.path.isfile(self.config['pidfile']):
                raise PIDExists('PID file %s already exists' % self.config['pidfile'])
            else:
                self.pidfile = self.config['pidfile']
                with open(self.pidfile, 'w') as fh:
                    fh.write(str(os.getpid()))
                atexit.register(self._cleanup)

    def _cleanup(self):
        """
        Cleanup actions
         - remove pid file
        """
        if self.pidfile:
            os.unlink(self.pidfile)

    def walk_tree(self, path, topdown=True):
        """
        Walk directory tree, similar to os.walk() but return File objects

        :param path: File object or string path
        :param topdown: pass from top down or from bottom to top
        :returns: 3-tuple like (File(root), [File(dir)], [File(file)])
        :rtype: tuple
        """
        if isinstance(path, File):
            # Called with File object as an argument
            root = path
            path = root.path
        else:
            root = File(path)

        files, dirs = [], []

        try:
            for item in os.listdir(path):
                file_path = os.path.join(path, item)

                if self.path_ignore and self.path_ignore.match(file_path):
                    # Skip excluded paths
                    lg.debug("Ignoring path %s" % file_path)
                    continue

                try:
                    f_object = File(file_path)
                except UnsupportedFileType as e:
                    lg.warn('%s ..skipping' % e)
                    continue
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        # File already removed, go on
                        lg.debug('File already removed: %s' % e)
                        continue
                    elif e.errno in [errno.EPERM, errno.EACCES]:
                        # Permission denied or operation not permitted, log error and go on
                        lg.error(e)
                        continue
                    else:
                        # Other errors should be fatal, but we don't want them to be
                        # eg. corrupted file on GlusterFS may raise IOError, but we want to continue
                        lg.exception(e)
                        continue

                if f_object.directory is True:
                    dirs.append(f_object)
                else:
                    files.append(f_object)
        except OSError as e:
            # Exceptions that may come from os.listdir()
            if e.errno == errno.ENOENT:
                # Directory doesn't exist, go on
                pass
            elif e.errno in [errno.EPERM, errno.EACCES]:
                # Permission denied or operation not permitted, log error and go on
                lg.error(e)
                pass
            else:
                # Other errors should be fatal, but we don't want them to be
                # eg. corrupted file on GlusterFS may raise IOError, but we want to go on
                lg.exception(e)
                pass

        if topdown:
            yield root, dirs, files

        for item in dirs:
            for x in self.walk_tree(item):
                yield x

        if not topdown:
            yield root, dirs, files

    def run(self):
        """
        Run cleanup
        """
        # Pass directory structure, gather files
        lg.warn("Passing %s" % self.config['path'])
        time_start = datetime.now()

        buffer_dirs = []
        for root, dirs, files in self.walk_tree(self.config['path'], topdown=True):
            for f_object in files:
                # Remove files immediately
                self.match_delete(f_object)

            for f_object in dirs:
                # Dirs have to be removed at last
                buffer_dirs.append(f_object)

        # Remove directories
        for f_object in buffer_dirs:
            self.match_delete(f_object)

        self.time_run = datetime.now() - time_start

    def match_delete(self, file):
        """
        Remove file if it matches at least one definition

        :param file: instance of File class
        """
        for definition in self.definitions:
            # Check if file matches definition path (or path is not specified)
            if definition.match_path(file):
                # Check if file matches time (return True if we don't want to match time)
                if definition.match_time(file):
                    if definition.no_remove is False:
                        ftype = 'directory' if file.directory is True else 'file'
                        lg.info("Removing %s %s, matching definition %s" % (ftype, file.path, definition.name))
                        if not self.dry:
                            try:
                                file.remove()
                            except OSError as e:
                                # Directory not empty or file or directory doesn't exist, these errors are fine
                                # just log them and go on
                                if e.errno in [errno.ENOENT, errno.ENOTEMPTY]:
                                    lg.info(e)
                                elif e.errno in [errno.EPERM, errno.EACCES]:
                                    # Permission denied or operation not supported, log error but go on
                                    file.failed = True
                                    lg.error(e)
                                else:
                                    # This could be worse error, raise
                                    raise
                        else:
                            # Set removed flag manually in dry-run
                            file.removed = True
                        break
                    else:
                        lg.debug("File %s matches definition %s, but we don't want to remove it" % (file.path, definition.name))
                else:
                    lg.debug("File %s matches path definition %s but haven't passed time match" % (file.path, definition.name))
                # Break if we have found correct definition by path and if pathMatch was specified
                #   - to avoid deleting file by more common definition
                #   - it would be good to have an option to overwrite this behavior if requested
                # also break if we have already removed the file by time
                if definition.path_match or file.removed:
                    break

        self.update_summary(file)
        return file

    def update_summary(self, f_object):
        """
        Update summary statistics

        :param f_object: File object
        """
        if f_object.directory:
            category = 'dirs'
        else:
            category = 'files'

        if f_object.failed:
            status = 'failed'
        elif f_object.removed:
            status = 'removed'
        else:
            status = 'existing'

        self.summary[f_object.definition][status][category] += 1

    def get_summary(self):
        """
        Return summary

        :return: dict
        """
        return self.summary


class File(object):
    """
    Represents single file or directory
    """
    def __init__(self, path, fstat=None):
        """
        Initialize object, stat file if stat is empty

        :param path: full path to a file
        :param fstat: posix.stat_result (output of os.stat())
        """
        self.path = path
        self.stat = os.stat(path) if not fstat else fstat
        assert isinstance(self.stat, posix.stat_result), "Stat is not instance of posix.stat_result"

        self.directory = stat.S_ISDIR(self.stat.st_mode)
        self.definition = None
        self.failed = None
        self.removed = False

        self.atime = datetime.fromtimestamp(self.stat.st_atime)
        self.mtime = datetime.fromtimestamp(self.stat.st_mtime)
        self.ctime = datetime.fromtimestamp(self.stat.st_ctime)

        # Check if it's file or directory, otherwise raise exception
        if not self.directory and not stat.S_ISREG(self.stat.st_mode):
            raise UnsupportedFileType("File %s is not regular file or directory" % path)

    def remove(self):
        """
        Remove file or directory
        """
        if self.directory:
            os.rmdir(self.path)
        else:
            os.unlink(self.path)

        self.removed = True


class Definition(object):
    """
    Cleanup definition
    """
    _ids = count(0)

    def __init__(self, name=None, pathMatch=None, pathExclude=None, filesOnly=False, noRemove=False, mtime=None, atime=None, ctime=None):
        """
        Setup variables
        """
        self.ids = self._ids.next()
        self.name = name if name else self.ids

        self.path_match = re.compile(pathMatch) if pathMatch else pathMatch
        self.path_exclude = re.compile(pathExclude) if pathExclude else pathExclude
        self.files_only = filesOnly
        self.no_remove = noRemove

        self.mtime = mtime
        self.atime = atime
        self.ctime = ctime

    def match_path(self, file):
        """
        Return True if object matches given definition path or if path is empty

        :param file: instance of File
        :returns: True if object matches definition
        :rtype: bool
        """
        # Check if path is excluded
        if self.path_exclude:
            if self.path_exclude.match(file.path):
                return False

        # Check if path matches
        if self.path_match:
            if not self.path_match.match(file.path):
                return False
            else:
                # File matches path, set definition for statistical purposes (even if it doesn't match the rest)
                # only if it already didn't match another filter
                if not file.definition:
                    file.definition = self.name

        return True

    def match_time(self, file):
        """
        Return True if object matches given mtime/ctime/atime

        :param file: instance of File
        :returns: True if object matches time definition
        :rtype: bool
        """
        # Check mtime/ctime/atime
        now = datetime.now()
        if self.atime:
            delta = timedelta(hours=self.atime)
            if (now - delta) < file.atime:
                return False

        if self.mtime:
            delta = timedelta(hours=self.mtime)
            if (now - delta) < file.mtime:
                return False

        if self.ctime:
            delta = timedelta(hours=self.ctime)
            if (now - delta) < file.ctime:
                return False

        # File matches definition - set it in file object for statistical purposes
        if not file.definition:
            file.definition = self.name

        return True


## Exceptions
class UnsupportedFileType(Exception):
    pass

class PIDExists(Exception):
    pass

class InvalidConfiguration(Exception):
    pass

class NoConfigFile(Exception):
    pass
