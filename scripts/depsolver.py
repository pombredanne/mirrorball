#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import os
import sys

mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

from updatebot import config
from updatebot import cmdline
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1] )

ui = cmdline.UserInterface()

pkgSource = pkgsource.PackageSource(cfg, ui)
pkgSource.load()

reqSrcPkgs = set()
for pkgName in cfg.package:
    bins = sorted(pkgSource.binNameMap.get(pkgName, []))
    if not bins:
        continue
    reqSrcPkgs.add(pkgSource.binPkgMap[bins[-1]])

reqBinPkgs = set()
for srcPkg in reqSrcPkgs:
    reqBinPkgs.update(set([ x for x in pkgSource.srcPkgMap[srcPkg]
                            if x.arch not in ('nosrc', 'src') ]))

requires = {}
provides = {}
log.info('loading package requires/provides')
for bin, src in pkgSource.binPkgMap.iteritems():
    if bin.arch in ('nosrc', 'src'):
        continue
    for format in bin.format:
        if format.getName() == 'rpm:provides':
            bins = set([ x.name for x in pkgSource.srcPkgMap[src]
                         if x.arch not in ('nosrc', 'src') ])
            for child in format.iterChildren():
                provides.setdefault(child.name, set()).update(bins)
        if format.getName() == 'rpm:requires':
            for child in format.iterChildren():
                requires.setdefault(bin.name, set()).add(child.name)


solved = set()
working = set([ x.name for x in reqBinPkgs ])

log.info('resolving deps')
while working:
    pkg = working.pop()
    log.info('resolving %s' % pkg)
    for req in requires[pkg]:
        if req.startswith('rpmlib'):
            continue
        if req not in provides:
            log.warn('requirement not found: %s' % req)
            continue
        for provPkg in provides[req]:
            if provPkg not in solved and provPkg != pkg:
                working.add(provPkg)

    solved.add(pkg)
    log.info('solved: %s, working set: %s' % (len(solved), len(working)))

needed = set()
for pkgName in solved:
    bins = sorted(pkgSource.binNameMap[pkgName])
    src = pkgSource.binPkgMap[bins[-1]]
    if src in reqSrcPkgs:
        continue
    pkgs = sorted([ x for x in pkgSource.srcPkgMap[src]
                    if x.arch not in ('nosrc', 'src') ])
    needed.add(pkgs[0])

import epdb; epdb.st()
