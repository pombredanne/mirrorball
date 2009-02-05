#!/usr/bin/python

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/epdb')

from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

from updatebot import config
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')

pkgSource = pkgsource.PackageSource(cfg)
pkgSource.load()

import epdb; epdb.st()
