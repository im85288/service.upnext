# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements file helper functions used elsewhere in the addon"""

from __future__ import absolute_import, division, unicode_literals
import errno
import xbmc
import xbmcvfs


def make_legal_filename(filename, prefix='', suffix=''):
    """Returns a legal filename, from an arbitrary string input, as a string"""

    filename = ''.join((
        prefix,
        filename,
        suffix
    ))
    try:
        filename = xbmcvfs.makeLegalFilename(filename)
    except AttributeError:
        xbmcvfs.makeLegalFilename = xbmc.makeLegalFilename
        filename = xbmcvfs.makeLegalFilename(filename)

    if filename.endswith('/'):
        filename = filename[:-1]
    return filename


def translate_path(path):
    """Returns a real path, translated from a special:// path, as a string"""

    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        xbmcvfs.translatePath = xbmc.translatePath
        return xbmcvfs.translatePath(path)


def create_directory(path):
    """Create a directory from a path string"""

    try:
        if not (xbmcvfs.exists(path) or xbmcvfs.mkdirs(path)):
            raise IOError(path)
    except (IOError, OSError) as error:
        if error.errno != errno.EEXIST:
            raise
    return True
