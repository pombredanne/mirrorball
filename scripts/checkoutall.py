#!/usr/bin/python
#
# Copryright (c) 2008 rPath, Inc.
#

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary import checkin
from updatebot import conaryhelper, config, log

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')
helper = conaryhelper.ConaryHelper(cfg)

pkgs = [ name for name, version, flavor in helper.getSourceTroves(cfg.topGroup) if version.trailingLabel().asString() == cfg.topGroup[1] ]
checkin.checkout(helper._repos, helper._ccfg, None, pkgs)