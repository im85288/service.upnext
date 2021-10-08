# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements file helper functions used elsewhere in the addon"""

from __future__ import absolute_import, division, unicode_literals
import errno
import os.path
import xbmc
import xbmcvfs


def _translate_path(path):
    """Returns a real path, translated from a special:// path, as a string"""

    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        xbmcvfs.translatePath = xbmc.translatePath
        return xbmcvfs.translatePath(path)


def sanitise(string):
    return ''.join('_' if i in '\\/:*?"<>| ' else i for i in string)


def get_legal_filename(filename, path='', prefix='', suffix=''):
    """Returns a legal filename, from an arbitrary string input, as a string"""

    # xbmcvfs.makeLegalFilename doesn't actually do what it is meant to do - it
    # creates a legal path, not a legal filename. Try to workaround issue here
    filename = sanitise(filename)
    filename = ''.join((prefix, filename, suffix))

    try:
        filename = xbmcvfs.makeLegalFilename(filename)
    except AttributeError:
        xbmcvfs.makeLegalFilename = xbmc.makeLegalFilename
        filename = xbmcvfs.makeLegalFilename(filename)

    if path:
        filename = os.path.join(get_legal_path(path), filename)

    return filename


def get_legal_path(path):
    """Returns a legal path, with a trailing path separator, from an arbitrary
       string input, as a string"""

    try:
        path = xbmcvfs.makeLegalFilename(_translate_path(path))
    except AttributeError:
        xbmcvfs.makeLegalFilename = xbmc.makeLegalFilename
        path = xbmcvfs.makeLegalFilename(_translate_path(path))

    return os.path.join(path, '')


def create_directory(path):
    """Create a directory from a path string"""

    try:
        if not (xbmcvfs.exists(path) or xbmcvfs.mkdirs(path)):
            raise IOError(path)
    except (IOError, OSError) as error:
        if error.errno != errno.EEXIST:
            raise
    return True
