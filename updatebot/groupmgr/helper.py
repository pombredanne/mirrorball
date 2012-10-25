#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


"""
Conary interface for group content management.
"""

import os
import time
import logging

from updatebot.lib import util
from updatebot.conaryhelper import ConaryHelper

from updatebot.groupmgr.model import GroupModel
from updatebot.groupmgr.model import GroupContentsModel

log = logging.getLogger('updatebot.groupmgr')

GROUP_RECIPE = """\
#
# Copyright (c) %(year)s rPath, Inc.
# This file is distributed under the terms of the MIT License.
# A copy is available at http://www.rpath.com/permanent/mit-license.html
#
class %%(className)s(FactoryRecipeClass):
    \"\"\"
    Groups require that a recipe exists.
    \"\"\" 
""" % {'year': time.gmtime().tm_year, }


class GroupHelper(ConaryHelper):
    """
    Modified conary helper to deal with managing group sources.
    """

    def __init__(self, cfg):
        ConaryHelper.__init__(self, cfg)
        self._configDir = cfg.configPath
        self._newPkgFactory = 'managed-group'
        self._groupContents = cfg.groupContents

        # FIXME: autoLoadRecipes causes group versioning to go sideways
        # The group super class in the repository has a version defined, which
        # overrides the version from factory-version. This should probably be
        # considered a bug in factory-managed-group, but we don't need
        # autoLoadRecipes here anyway.
        self._ccfg.autoLoadRecipes = []

    def _newpkg(self, pkgName):
        """
        Wrap newpkg to add a group recipe since group recipes are required.
        """

        recipeDir = ConaryHelper._newpkg(self, pkgName)

        recipe = '%s.recipe' % pkgName
        recipeFile = os.path.join(recipeDir, recipe)
        if not os.path.exists(recipeFile):
            className = util.convertPackageNameToClassName(pkgName)
            fh = open(recipeFile, 'w')
            fh.write(GROUP_RECIPE % {'className': className})
            fh.close()
            self._addFile(recipeDir, recipe)

        return recipeDir

    def getModel(self, pkgName, version=None):
        """
        Get a thawed data representation of the group xml data from the
        repository.
        """

        log.info('loading model for %s' % pkgName)
        recipeDir = self._edit(pkgName, version=version)
        groupFileName = util.join(recipeDir, 'groups.xml')

        # load group model
        groups = {}
        if os.path.exists(groupFileName):
            model = GroupModel.thaw(groupFileName)
            for name, groupObj in model.iteritems():
                contentFileName = util.join(recipeDir, groupObj.filename)
                contentsModel = GroupContentsModel.thaw(contentFileName,
                                (name, groupObj.byDefault, groupObj.depCheck,
                                 groupObj.checkPathConflicts))
                contentsModel.fileName = groupObj.filename
                groups[groupObj.name] = contentsModel

        return groups

    def setModel(self, pkgName, groups, version=None):
        """
        Freeze group model and save to the repository.
        """

        log.info('saving model for %s' % pkgName)
        recipeDir = self._edit(pkgName, version=version)
        groupFileName = util.join(recipeDir, 'groups.xml')

        groupModel = GroupModel()
        for name, model in groups.iteritems():
            groupfn = util.join(recipeDir, model.fileName)

            model.freeze(groupfn)
            groupModel.add(name=name,
                           filename=model.fileName,
                           byDefault=model.byDefault,
                           depCheck=model.depCheck,
                           checkPathConflicts=model.checkPathConflicts,)
            self._addFile(recipeDir, model.fileName)

        groupModel.freeze(groupFileName)
        self._addFile(recipeDir, 'groups.xml')

    def getErrataState(self, pkgname, version=None):
        """
        Get the contents of the errata state file from the specified package,
        if file does not exist, return None.
        """

        log.info('getting errata state information from %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        stateFileName = util.join(recipeDir, 'erratastate')

        if not os.path.exists(stateFileName):
            return None

        state = open(stateFileName).read().strip()
        if state.isdigit():
            state = int(state)
        return state

    def setErrataState(self, pkgname, state, version=None):
        """
        Set the current errata state for the given package.
        """

        log.info('storing errata state information in %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        stateFileName = util.join(recipeDir, 'erratastate')

        # write state info
        statefh = open(stateFileName, 'w')
        statefh.write(str(state))

        # source files must end in a trailing newline
        statefh.write('\n')

        statefh.close()

        # make sure state file is part of source trove
        self._addFile(recipeDir, 'erratastate')
