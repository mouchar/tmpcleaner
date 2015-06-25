# -*- coding: utf-8 -*-
# Copyright (C) 2007-2014, GoodData(R) Corporation. All rights reserved

"""
Initialize logging

Initialize:
import tmpcleaner.logger as logger
import logging
logger.init()
lg = logging.getLogger('application')
lg.info("Logger loaded")

Usage:
import logging
lg = logging.getLogger('application')
"""

import logging
import logging.handlers
from gdctmpcleaner.logger.level_handler import LevelHandler

lg = None

# Initialize logging
def init(name='', level=logging.WARN, syslog=True, console=True):
    global lg

    lg = logging.getLogger(name)
    lg.setLevel(level)

    if console:
        lg_console = LevelHandler()
        lg_console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

        lg.addHandler(lg_console)

    if syslog:
        lg_syslog = logging.handlers.SysLogHandler(
            facility=logging.handlers.SysLogHandler.LOG_LOCAL5,
            address='/dev/log')
        lg_syslog.setFormatter(logging.Formatter('%(name)-9s %(levelname)-8s %(message)s'))

        lg.addHandler(lg_syslog)

    return lg
