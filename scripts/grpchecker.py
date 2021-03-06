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


"""
Script for finding and fixing group issues.
"""

from _scriptsetup import mirrorballDir as mbdir
import os
import sys


from conary import versions
from conary.conaryclient import cmdline

confDir = os.path.join(mbdir, 'config', sys.argv[1])

sourceVersion = None
if len(sys.argv) == 3:
    sourceVersion = cmdline.parseTroveSpec(sys.argv[2])[1]

from updatebot import log
from updatebot import groupmgr
from updatebot import pkgsource
from updatebot import conaryhelper
from updatebot import UpdateBotConfig
from updatebot.cmdline import UserInterface

from updatebot.errors import OldVersionsFoundError
from updatebot.errors import GroupValidationFailedError
from updatebot.errors import NameVersionConflictsFoundError
from updatebot.errors import ExpectedRemovalValidationFailedError

slog = log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

ui = UserInterface()

pkgSource = pkgsource.PackageSource(cfg, ui)
pkgSource.load()

mgr = groupmgr.GroupManager(cfg, ui, useMap=pkgSource.useMap)
helper = conaryhelper.ConaryHelper(cfg)

def handleVersionConflicts(group, error):
    conflicts = error.conflicts
    binPkgs = error.binPkgs

    toAdd = {}
    toRemove = set()
    for source, svers in conflicts.iteritems():
        assert len(svers) == 2
        svers.sort()
        old = binPkgs[(source, svers[0], None)]
        new = binPkgs[(source, svers[1], None)]

        toRemove.update(set([ x[0] for x in old ]))

        for n, v, f, in new:
            if n in toRemove:
                toAdd.setdefault((n, v), set()).add(f)

    return toRemove, toAdd

def handleVersionErrors(group, error):
    toAdd = {}
    toRemove = set()
    for pkgName, (modelContents, repoContents) in error.errors.iteritems():
        toRemove.update(set([ x[0] for x in modelContents ]))

        for n, v, f in repoContents:
            if n in toRemove:
                toAdd.setdefault((n, v), set()).add(f)

    return toRemove, toAdd

def handleRemovalErrors(group, error):
    toAdd = {}
    toRemove = set(error.pkgNames)

    return toRemove, toAdd

def checkVersion(ver):
    grp = mgr.getGroup(version=ver)
    grp._copyVersions()

    changes = []

    try:
        grp._sanityCheck()
    except GroupValidationFailedError, e:
        for group, error in e.errors:
            if isinstance(error, NameVersionConflictsFoundError):
                changes.append(handleVersionConflicts(group, error))
            elif isinstance(error, OldVersionsFoundError):
                changes.append(handleVersionErrors(group, error))
            elif isinstance(error, ExpectedRemovalValidationFailedError):
                changes.append(handleRemovalErrors(group, error))
            else:
                raise error

    return ver, changes

srcName, srcVersion, srcFlavor = cfg.topSourceGroup
troves = helper.findTrove(('%s:source' % srcName, srcVersion, srcFlavor), getLeaves=False)

troveSpec = ('%s:source' % cfg.topSourceGroup[0], sourceVersion, None)
sourceVersion = helper.findTroves((troveSpec, )).values()[0][0][1]

nv = []
start = False
for n, v, f in sorted(troves):
    if sourceVersion and v == sourceVersion:
        start = True
    if not start:
        continue
    nsv = (n, v.getSourceVersion())
    if nsv not in nv:
        nv.append(nsv)

if not start:
    raise RuntimeError

toUpdate = []
for n, v in nv:
    ver, changed = checkVersion(v)
    # Make sure to only rebuild groups that have changed
    # and every group after.
    if not changed and not toUpdate:
        continue
    toUpdate.append((ver, changed))

#slog.critical('Before going any further, be aware that this will only rebuild '
#    'the groups that need to change, not any other existing groups, if you '
#    'want to maintain order on the devel label you will need to write that '
#    'code.')
#assert False

import epdb; epdb.st()

jobIds = []
removed = {}
for ver, changed in toUpdate:
    grp = mgr.getGroup(version=ver)

    slog.info('updating %s' % ver)

    # Find all names and versions in the group model
    nv = dict([ (y.name, versions.ThawVersion(y.version))
                for x, y in grp._groups[grp._pkgGroupName].iteritems() ])

    # Set of packages that should be removed
    removals = set([ x for x, y in removed.iteritems() if nv[x] == y ])

    # Remove old removals
    for pkg in removals:
        slog.info('removing %s' % pkg)
        grp.removePackage(pkg)

    for toRemove, toAdd in changed:
        # Handle removes
        for pkg in toRemove:
            slog.info('removing %s' % pkg)
            grp.removePackage(pkg)

            # cache removals
            removed[pkg] = nv[pkg]

        # Handle adds
        for (n, v), flvs in toAdd.iteritems():
            slog.info('adding %s=%s' % (n, v))
            grp.addPackage(n, v, flvs)

    grp._copyVersions()
    grp._sanityCheck()
    mgr._persistGroup(grp)

    import epdb; epdb.st()

    newGroup = grp.commit(copyToLatest=True)
    jobId = mgr._builder.start(((mgr._sourceName, newGroup.conaryVersion, None), ))
    jobIds.append(jobId)

for jobId in jobIds:
    mgr._builder.watch(jobId)

#import epdb; epdb.st()

for jobId in jobIds:
    mgr._builder.commit(jobId)

import epdb; epdb.st()
