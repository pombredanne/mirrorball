#
# Copyright (c) 2009 rPath, Inc.
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

"""
Module for serializable representations of repository metadata.
"""

from xobj import xobj

from aptmd.packages import _Package
from aptmd.sources import _SourcePackage

class XDocManager(xobj.Document):
    """
    Base class that implements simple freeze/thaw methods.
    """

    data = str

    freeze = xobj.Document.toxml

    @classmethod
    def thaw(cls, xml):
        """
        Deserialize an xml string into a DocManager instance.
        """

        return xobj.parse(xml, documentClass=cls)


class XMetadata(object):
    """
    Representation of repository data.
    """

    binaryPackages = [ _Package ]
    sourcePackage = _SourcePackage


class XMetadataDoc(XDocManager):
    """
    Document class for repository data.
    """

    data = XMetadata

    def __init__(self, *args, **kwargs):
        data = kwargs.pop('data', None)
        XDocManager.__init__(self, *args, **kwargs)
        if data is not None:
            self.data = XMetadata()
            self.data.binaryPackages = []
            for pkg in data:
                if pkg.arch == 'src':
                    self.data.sourcePackage = pkg
                else:
                    self.data.binaryPackages.append(pkg)
