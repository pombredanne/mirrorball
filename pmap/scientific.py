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


import re
import logging
log = logging.getLogger('pmap.scientific')

from pmap.common import BaseParser
from pmap.common import BaseContainer

class ScientificLinuxAdvisory(BaseContainer):
    """
    Container class for Scientific Linux advisories.
    """

    _slots = ('pkgs', )

    def finalize(self):
        """
        Derive advisory information.
        """

        BaseContainer.finalize(self)


class Parser(BaseParser):
    """
    Parser for Scientific Linux mail archives.
    """

    def __init__(self, productVersion=None):
        BaseParser.__init__(self)

        self._containerClass = ScientificLinuxAdvisory
        self._states.update({
            'synopsis'  : self._synopsis,
            'Issue'     : None,
            'SLVersion' : self._slVersion,
            'Arch'      : self._arch,
            'End'       : self._end,
        })

        self._supportedArch = ('SRPM', 'SRPMS', 'i386', 'x86_64', )

        self._filterLine('^Issue date:.*', 'Issue')
        self._filter('^sl[0-9]\.x', 'SLVersion')
        self._filterLine('^SL [0-9]\.x', 'SLVersion')
        self._filterLine('^\s*(%s).*' % '|'.join(self._supportedArch), 'Arch')
        self._filterLine('^-*(Connie\ Sieh|Troy\ Dawson).*', 'End')

        self._productVersion = productVersion
        if productVersion:
            self._checkSubject = True
            self._subjectVersionRE = re.compile('.*SL[ ]{0,1}%s\.x.*' % productVersion)
        else:
            self._checkSubject = False

    def _getState(self, state):
        """
        Return a valid state based on input.
        """

        state = BaseParser._getState(self, state)
        if '\t' in state:
            state = state.split('\t')[0]
            if state.endswith(':'):
                state = state[:-1]
        return state

    def _newContainer(self):
        """
        Create a new container and reinitize any required vars.
        """

        BaseParser._newContainer(self)

        self._inVersion = None
        self._inArch = None
        self._descSet = False
        self._logged = False

    def _parseLine(self, line):
        """
        Check subject for correct version.
        """

        parse = not self._checkSubject
        # Check to see if the advisory might apply to the version that we
        # care about.
        if (self._curObj and self._checkSubject and
            self._subjectVersionRE.match(self._curObj.subject)):
            parse = True

        if parse:
            BaseParser._parseLine(self, line)
        elif not self._logged:
            self._logged = True
            log.warn('skipping message: %s' % self._curObj.subject)
            self._curObj = None

    def _addPkg(self, pkg):
        """
        Add package to container.
        """

        if self._curObj.pkgs is None:
            self._curObj.pkgs = set()
        if not pkg.endswith('.rpm'):
            return
        self._curObj.pkgs.add(pkg)

    def _synopsis(self):
        """
        Parse Synopsis: line.
        """

        self._curObj.summary = self._getLine()

    def _slVersion(self):
        """
        Parse SL Version.
        """

        line = self._getFullLine()
        assert line.startswith('SL')

        version = line.split('L')[1].strip()

        self._handleText()
        self._inVersion = version

    def _arch(self):
        """
        Parse arch.
        """

        self._handleText()

        arch = self._getFullLine().strip(':')
        if arch in self._supportedArch:
            self._inArch = arch
        else:
            self._inArch = None

    def _end(self):
        """
        Process anything left over in the text buffer now that we have reached
        the end of the message.
        """

        self._handleText()

    def _handleText(self):
        """
        Check the _text buffer to see if we it contains a description or list
        of packages.
        """

        # Probably previous was description.
        if not self._inVersion and not self._inArch and not self._descSet:
            self._curObj.description = self._text
            self._descSet = True

        # Probably in package section.
        elif self._text and self._inArch:

            # Bail out if this is not the product version that we are
            # looking for.
            if (self._inVersion and self._productVersion and
                not self._inVersion.startswith(self._productVersion)):
                return

            for pkg in [ x.strip() for x in self._text.split('\n')
                         if x.strip().endswith('.rpm') ]:
                self._addPkg(pkg)
