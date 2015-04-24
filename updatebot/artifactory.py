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
Module for finding artifactory packages and updating them
"""

from collections import deque
import logging
import time

from conary import conarycfg
from rmake.build import buildcfg
from rmake.cmdline import helper

from . import cmdline
from . import pkgsource
from .bot import Bot as BotSuperClass
from .build import Builder
from .errors import JobFailedError
from .lib import util
from .update import Updater as UpdaterSuperClass


log = logging.getLogger('updatebot.artifactory')


class Bot(BotSuperClass):

    _updateMode = 'artifactory'

    def __init__(self, cfg):
        self._validateMode(cfg)

        self._cfg = cfg

        self._clientcfg = cmdline.UpdateBotClientConfig()
        self._ui = cmdline.UserInterface(self._clientcfg)

        self._pkgSource = pkgsource.PackageSource(self._cfg, self._ui)
        self._updater = Updater(self._cfg, self._ui, self._pkgSource)

    def create(self, rebuild=False, recreate=None):
        """
        Do initial imports.

        :param bool rebuild: build all packages, even if source is the same
        :param bool recreate: recreate all source packages
        """
        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Import sources into repository.
        trvMap, fail = self._updater.create(buildAll=rebuild, recreate=recreate)

        if fail:
            log.error('failed to create %s packages:' % len(fail))
            for pkg, e in fail:
                log.error('failed to import %s: %s' % (pkg, e))
            return {}, fail

        log.info('elapsed time %s' % (time.time() - start, ))
        return trvMap, fail


class Updater(UpdaterSuperClass):
    """Class for finding and updating packages sourced from artifactory
    """

    def _buildLeaf(self, leaf, cache, buildAll=False, recreate=False):
        failedImports = set()
        srcVersion = cache.get((
            '%s:source' % leaf.name,
            leaf.getConaryVersion(),
            None,
            ))
        binVersion = cache.get((
            leaf.name,
            leaf.getConaryVersion(),
            None,
            ))

        # determine if leaf needs to be imported, and update srcVersion
        srcVersion = self._importPackage(leaf, srcVersion, recreate)

        # if buildAll is true, or there is no existing binary or the
        # binary was built from a different source, then build leaf
        if (buildAll or not binVersion
                or binVersion.getSourceVersion() != srcVersion):
            return srcVersion, True
        else:
            log.info('not building %s' % leaf)
            return srcVersion, False

    def _build(self, buildSet, buildReqs, cache):
        """Helper function to do some repetivite pre-build processing

        :param buildSet: list of name, version, flavor tuples and packages to
            build
        :type buildSet: [((name, version, flavor), package), ...]
        :param dict cache: conary version cache
        """
        # unpack buildSet into nvf tuples
        nvfs = []
        buildPackages = []
        resolveTroves = set()

        for package, version in buildSet:
            nvfs.append((package.name, version, None))
            buildPackages.append(package)

        # get our base rmakeCfg
        rmakeCfg = Builder(self._cfg, self._ui)._getRmakeConfig()

        # create resolve troves for deps not in the current chunk
        resolveTroves.update(set([
            (dep.name, rmakeCfg.buildLabel, dep.getConaryVersion())
            for dep in buildReqs
            if dep not in buildPackages
            ]))

        rmakeCfg.configKey(
            'resolveTroves',
            ' '.join('%s=%s/%s' % r for r in resolveTroves),
            )

        # make a new buidler with rmakeCfg to do the actual build
        builder = Builder(self._cfg, self._ui, rmakeCfg=rmakeCfg)

        # Build all newly imported packages.
        tries = 0
        while True:
            try:
                log.debug("Building: \n%s", "\n".join(str(nvf) for nvf in nvfs))
                log.debug("Resolve troves: \n%s",
                          "\n".join("%s=%s/%s" % r for r in resolveTroves))
                trvMap = builder.build(nvfs)
            except JobFailedError, e:
                # Commit partial job
                log.info('committing partial job %s', e.jobId)
                trvMap = builder._commitJob(e.jobId)
                break
                if tries > 1:
                    raise
                tries += 1
                log.info('attempting to retry build: %s of %s', tries, 2)
            else:
                break

        return trvMap

    def _createVerCache(self, troveList):
        verCache = {}
        for k, v in self._conaryhelper.findTroves(
                troveList,
                allowMissing=True,
                cache=False,
                ).iteritems():
            if len(v) > 1:
                # something weird happened
                import epdb; epdb.st()  # XXX breakpoint
            verCache[k] = v[0][1]  # v is a list of a tuple (name, ver, flav)
        return verCache

    def _importPackage(self, p, version, recreate):
        """Import source package

        If the package is new, or `recreate` is True, then check if the
        source needs to be updated.

        :param PomPackage p: package to import
        :param version: conary version of existing source
        :type version: conary version object or None
        :param bool recreate: re-import the package if True
        :returns: the conary source version to build
        :rtype: conary version object
        """
        if not version or recreate:
            log.info("attempting to import %s", p)

            manifest = dict(
                version=p.getConaryVersion(),
                build_requires=p.buildRequires,
                artifacts=p.artifacts,
                )

            if version and recreate:
                origManifest = self._conaryhelper.getJsonManifest(p.name, version)
                if manifest == origManifest:
                    return version

            self._conaryhelper.setJsonManifest(p.name, manifest)
            version = self._conaryhelper.commit(
                p.name, commitMessage=self._cfg.commitMessage)
        else:
            log.info("not importing %s", p)

        return version

    def create(self, buildAll=False, recreate=False):
        """Import new packages into the repository

        By default, this will only imort and build completely new packages. Set
        `buildAll` to True if you want to buid all packages, even ones whose
        source trove did not changes. Set `recreate` True if you want to check
        if existing sources changed, and import them if they have.

        :param buildAll: build all binary packages, even if their source didn't
            change, defaults to False
        :type buildAll: bool
        :param recreate: commit changed source packages when True, else only
            commit new sources
        :type recreate: bool
        :returns: a list of buildable chunks (sets of packages that can be built
            together)
        :rtype: [set([((name, version, flavor), pkg), ...]), ...]
        """
        # generate a list of trove specs for the packages in the queue so
        # we can populate a cache of existing conary versions
        troveList = []
        for p in self._pkgSource.pkgQueue.iterNodes():
            troveList.append((p.name, p.getConaryVersion(), None))
            troveList.append(('%s:source' % p.name, p.getConaryVersion(), None))

        fail = set()                    # packages that failed to import
        chunk = set()                   # current chunk of packages to build
        chunkedPackageNames = set()     # names of packages in the current chunk
        trvMap = {}                     # map of built troves
        verCache = self._createVerCache(troveList)  # initial version cache

        # walk our dependency graph by getting all of the current leaves,
        # figuring out which can built together, building those and then
        # reiterating the process with the new set of leaves
        addedAny = False
        graph = self._pkgSource.pkgQueue
        total = len(list(graph.iterNodes()))
        count = 0
        leaves = set(graph.getLeaves())
        job = set()               # set of leaves we can build together
        jobNames = set()          # names of leaves and their deps in job
        jobBuildReqs = set()      # leaves' build reqs
        while leaves:
            addedAny = False
            for leaf in leaves:
                try:
                    version, buildLeaf = self._buildLeaf(
                        leaf, verCache, buildAll, recreate)
                except Exception, e:
                    log.error('failed to import %s: %s' % (leaf, e))
                    raise

                if buildLeaf:
                    # defer this leaf to the next round if another
                    # version of the leaf or of any of its
                    # dependencies are building this round
                    deferLeaf = False
                    if leaf.name in jobNames or any(
                            (d.name in jobNames and d not in jobBuildReqs)
                            for d in leaf.dependencies):
                        deferLeaf = True

                    if not deferLeaf:
                        # add this leaf to the job
                        log.info("Building %s", leaf)
                        job.add((leaf, version))
                        jobNames.add(leaf.name)
                        jobBuildReqs.update(set(leaf.dependencies))
                        jobNames.update(
                            set([d.name for d in leaf.dependencies]))
                        graph.delete(leaf)
                        count += 1
                        addedAny = True
                else:
                    graph.delete(leaf)
                    count += 1

                if job and len(job) >= self._cfg.chunkSize:
                    break

            if job and not addedAny:
                results = self._build(job, jobBuildReqs, verCache)
                trvMap.update(results)
                log.info("Processed %s of %s", count, total)

                # update the version cache
                verCache = self._createVerCache(troveList)

                # clear the job
                job = set()
                jobNames = set()
                jobBuildReqs = set()
                jobBuildReqNames = set()
                addedAny = False

            leaves = set(graph.getLeaves())

        # build the last job
        if job:
            trvMap.update(self._build(job, jobBuildReqs, verCache))
            log.info("Processed %s of %s", count, total)

        return trvMap, fail
