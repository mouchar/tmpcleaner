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
import time

import logging
lg = logging.getLogger('tmpcleaner')


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
        self.time_pass = timedelta(seconds=0)
        self.time_remove = timedelta(seconds=0)

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
                'failed': {'dirs': 0, 'files': 0, 'size': 0},
                'removed': {'dirs': 0, 'files': 0, 'size': 0},
                'existing': {'dirs': 0, 'files': 0, 'size': 0},
            }
        }

        for definition in self.definitions:
            self.summary[definition.name] = {
                'failed': {'dirs': 0, 'files': 0, 'size': 0},
                'removed': {'dirs': 0, 'files': 0, 'size': 0},
                'existing': {'dirs': 0, 'files': 0, 'size': 0},
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

        # Cache for unprocessed records
        self.st = {}

    def errh(self, exc):
        """
        Error-handling function for os.walk
        """
        if exc.errno == errno.ENOENT:
            # Directory doesn't exist, go on
            pass
        elif exc.errno in [errno.EPERM, errno.EACCES]:
            # Permission denied or operation not permitted, log error and go on
            lg.error(exc)
        else:
            # Other errors should be fatal, but we don't want them to be
            # eg. corrupted file on GlusterFS may raise IOError, but we want to go on
            lg.exception(exc)

    def _cleanup(self):
        """
        Cleanup actions
         - remove pid file
        """
        if self.pidfile:
            os.unlink(self.pidfile)

    def walk_tree(self, top):
        """
        Walk directory tree, uses os.walk()

        :param top: string path where to start
        """
        for root, dirs, files in os.walk(top, topdown=False, onerror=self.errh):
            self.st.update({root: {'files': list(files), 'dirs': list(dirs)}})
            # Handle path_ignore
            if self.path_ignore and self.path_ignore.match(root):
                continue
            for name in files:
                fname = os.path.join(root, name)
                try:
                    curr = File(fname)
                except UnsupportedFileType as exc:
                    lg.warn('%s ..skipping' % exc)
                    continue
                curr = self.match_delete(curr)
                if curr.removed:
                    self.st[root]['files'].remove(name)
            for name in dirs:
                fname = os.path.join(root,name)
                try:
                    curr = File(fname)
                except UnsupportedFileType as exc:
                    lg.warn('%s ..skipping' % exc)
                    continue
                if self.st[fname]['files'] or self.st[fname]['dirs']:
                    # This dir still has some files/dirs, we'll preserve it
                    for d in self.st[fname]['dirs']:
                        # but we can remove already processed children to save memory
                        del self.st[os.path.join(fname, d)]
                else:
                    curr = self.match_delete(curr)
                    if curr.removed:
                        self.st[root]['dirs'].remove(name)
                        del self.st[fname]
                    else:
                        # Preserve not matching directory
                        for d in self.st[fname]['dirs']:
                            # but remove it from cache
                            del self.st[os.path.join(fname, d)]

    def run(self):
        """
        Run cleanup
        """
        # Pass directory structure, gather files
        lg.warn("Passing %s" % self.config['path'])
        time_start = datetime.now()

        self.walk_tree(self.config['path'])
        self.time_run = datetime.now() - time_start

    def match(self, file):
        """
        Matches at least one definition?

        :param file: instance of File class
        :return: matching definition/None
        """
        for definition in self.definitions:
            # Check if file matches definition path (or path is not specified)
            if definition.match_path(file):
                # Check if file matches time (return True if we don't want to
                # match time)
                if definition.match_time(file):
                    if definition.no_remove is False:
                        return definition
                    else:
                        lg.debug("File %s matches definition %s, but we don't "
                                 "want to remove it", file.path,
                                 definition.name)
                else:
                    lg.debug("File %s matches path definition %s but haven't "
                             "passed time match", file.path, definition.name)
                # Break if we have found correct definition by path and if
                # pathMatch was specified
                #   - to avoid deleting file by more common definition
                #   - it would be good to have an option to overwrite this
                #     behavior if requested
                # also break if we have already removed the file by time
                if definition.path_match or file.removed:
                    break

        return None

    def match_delete(self, file):
        """
        Remove file if it matches at least one definition

        :param file: instance of File class
        """

        not_deleted = False
        matching_definition = self.match(file)
        if matching_definition:
            ftype = 'directory' if file.directory else 'file'
            lg.info("Removing %s %s, matching definition %s",
                    ftype, file.path, matching_definition.name)
            if not self.dry:
                try:
                    file.remove()
                except OSError as e:
                    # Directory not empty or file or directory doesn't exist,
                    # these errors are fine just log them and go on
                    if e.errno in [errno.ENOENT, errno.ENOTEMPTY]:
                        not_deleted = True
                        lg.info(e)
                    elif e.errno in [errno.EPERM, errno.EACCES]:
                        # Permission denied or operation not supported,
                        # log error but go on
                        file.failed = True
                        lg.error(e)
                    else:
                        # This could be worse error, raise
                        raise
            else:
                # Set removed flag manually in dry-run
                file.removed = True
        # don't count dirs with subdirs
        if matching_definition and not_deleted:
            return file
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

        # Update size statistics
        if not f_object.directory and f_object.stat.st_size:
            self.summary[f_object.definition][status]['size'] += f_object.stat.st_size

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

        self.atime = self.stat.st_atime
        self.mtime = self.stat.st_mtime
        self.ctime = self.stat.st_ctime

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

    def __init__(self, name=None, pathMatch=None, pathExclude=None, noRemove=False, mtime=None, atime=None, ctime=None):
        """
        Setup variables
        """
        self.ids = self._ids.next()
        self.name = name if name else self.ids

        self.path_match = re.compile(pathMatch) if pathMatch else None
        self.path_exclude = re.compile(pathExclude) if pathExclude else None
        self.no_remove = noRemove

        self.mtime = 3600 * mtime if mtime else None
        self.atime = 3600 * atime if atime else None
        self.ctime = 3600 * ctime if ctime else None

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
        now = time.time()
        if self.atime and (now - self.atime) < file.atime:
            return False

        if self.mtime and (now - self.mtime) < file.mtime:
            return False

        if self.ctime and (now - self.ctime) < file.ctime:
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
