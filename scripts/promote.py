#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.
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

from header import *

from updatebot import conaryhelper
helper = conaryhelper.ConaryHelper(cfg)

from conary import versions
from conary.deps import deps

import logging
slog = logging.getLogger('script')

trvLst = helper._repos.findTrove(helper._ccfg.buildLabel, cfg.topGroup)
trvLst = helper._findLatest(trvLst)

cs, packages = helper.promote(
    trvLst,
    [],
    cfg.sourceLabel,
    cfg.targetLabel,
    checkPackageList=False,
    extraPromoteTroves=cfg.extraPromoteTroves,
    commit=False
)

newPkgs = set([ (x[0].split(':')[0], x[1].getSourceVersion(), x[2]) for x in packages])

pkgMap = {}
for n, v, f in newPkgs:
    if (n, v) not in pkgMap:
        pkgMap[(n, v)] = set()
    pkgMap[(n, v)].add(f)

pkgs = pkgMap.keys()
pkgs.sort()

for pkg in pkgs:
    if pkg[0].startswith('group-'):
        continue
    for flv in pkgMap[pkg]:
        if len(pkgMap[pkg]) > 1 and flv == deps.Flavor():
            continue
        slog.info('promoting %s=%s[%s]' % (pkg[0], pkg[1], flv))

slog.info('committing')

helper._repos.commitChangeSet(cs)

slog.info('done')
