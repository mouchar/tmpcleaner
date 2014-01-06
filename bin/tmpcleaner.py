#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2013, GoodData(R) Corporation. All rights reserved

"""
Simple temp cleaner with support for statistics and multiple filter definitions.

Note that this tool doesn't support option similar to mindepth, you have to specify full pathMatch or pathExclude options.
Take care about definitions order - first match has precedence so common rules should be last.
Definition options have to be matched all, otherwise file/directory won't pass the definition (except for pathMatch option
that is also used for statistics grouping)
Don't use definitions without atime/mtime/ctime or it may remove all items in directory tree.

This tool currently supports only files and directories, it will just skip other file types with error.

Config options:
    pidfile - file for PID, if empty, then PID won't be saved
    path    - path to pass and cleanup
    pathIgnore - regular expression for path to ignore, eg. '.*/\.snapshot(/.*|$)' to ignore directories named .snapshot

Config options per definition:
    name    - friendly name for classification (otherwise id will be used)
    pathMatch   - regular expression for path to match
    pathExclude - regular expression for path to exclude
    filesOnly   - ignore directories
    noRemove    - don't remove files/directories, good for statistical classification
    atime       - filter by access time (hour)
    mtime       - filter by modification time (hour)
    ctime       - filter by last status change time (hour)


Example yaml config file:

    ---
    pidfile:    /var/run/tmpcleaner.pid
    path:       /tmp
    pathIgnore: '.*/\.snapshot(/.*|$)'

    definitions:
      - # Always remove file test when found
        name: test
        pathMatch: '.*/test$'
      - # Cleanup files with mtime more than 1 day
        name: users
        pathMatch: '/tmp/users/.*/.*/.*'
        mtime: 24
      - # Never cleanup projects, print just statistics
        name: projects
        pathMatch: '/tmp/projects/.*/.*/.*'
        noRemove: true
"""

import sys
import argparse

import logging
import tmpcleaner.logger

from tmpcleaner import TmpCleaner, InvalidConfiguration, PIDExists, NoConfigFile

global lg

def main():
    """
    Main entrance
    """
    global lg

    parser = argparse.ArgumentParser(description='Smart temp cleaner')
    parser.add_argument('config', help='Config file to use')
    parser.add_argument('--dry', action='store_true', help='Dry run only')
    parser.add_argument('-v', '--verbose', action='store_true', help='Be verbose')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
    parser.add_argument('-q', '--quiet', action='store_true', help='Be quiet (no console logging)')
    args = parser.parse_args()

    if args.quiet:
        lg = tmpcleaner.logger.init(console=False)
    else:
        lg = tmpcleaner.logger.init()

    if args.verbose:
        lg.setLevel(logging.INFO)

    if args.debug:
        lg.setLevel(logging.DEBUG)

    try:
        cleaner = TmpCleaner(args.config, dry=args.dry)
        cleaner.run()
    except (InvalidConfiguration, PIDExists, NoConfigFile) as e:
        # "Friendly" exceptions, no stack-trace, just log them
        lg.error(e)
        sys.exit(1)
    except Exception as e:
        lg.exception(e)
        sys.exit(1)

    summary = cleaner.get_summary()
    totals = {
        'removed_files': 0,
        'removed_dirs': 0,
        'removed_size': 0,
        'existing_files': 0,
        'existing_dirs': 0,
        'existing_size': 0,
        }

    # Print per-definition summary
    for name, definition in summary.iteritems():
        if name is None:
            name = 'unspecified'

        report = 'Summary: path={0} definition={1} removed_files={removed[files]} removed_dirs={removed[dirs]} removed_size={removed[size]} existing_files={existing[files]} existing_dirs={existing[dirs]} existing_size={existing[size]}'.format(cleaner.config['path'], name, **definition)
        totals['removed_files'] += definition['removed']['files']
        totals['removed_dirs'] += definition['removed']['dirs']
        totals['removed_size'] += definition['removed']['size']
        totals['existing_files'] += definition['existing']['files']
        totals['existing_dirs'] += definition['existing']['dirs']
        totals['existing_size'] += definition['existing']['size']
        lg.warn(report)

    # Print totals
    report = 'Summary totals: path={0} time={1} removed_files={removed_files} removed_dirs={removed_dirs} removed_size={removed_size} existing_files={existing_files} existing_dirs={existing_dirs} existing_size={existing_size}'\
        .format(cleaner.config['path'], cleaner.time_run.seconds, **totals)
    lg.warn(report)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        lg.info("Interrupted")
        sys.exit(1)
