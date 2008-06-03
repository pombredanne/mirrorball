#
# Copyright (c) 2008 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

'''
Module of logging related functions.
'''

import sys
import logging

def addRootLogger():
    '''
    Setup the root logger that should be inherited by all other loggers.
    '''

    rootLog = logging.getLogger('')
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s '
        '%(name)s %(message)s')
    handler.setFormatter(formatter)
    rootLog.addHandler(handler)
    rootLog.setLevel(logging.INFO)

    # Delete conary's log handler since it puts things on stderr and without
    # any timestamps.
    conaryLog = logging.getLogger('conary')
    for handler in conaryLog.handlers:
        conaryLog.removeHandler(handler)