# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
''' This file implements the Kodi xbmcvfs module, either using stubs or alternative functionality '''

# pylint: disable=invalid-name

from __future__ import absolute_import, division, print_function, unicode_literals
import os
from xbmcextra import __KODI_MATRIX__


class File:
    ''' A reimplementation of the xbmcvfs File() function '''
    def __init__(self, path, mode=None):
        if mode != 'w':
            mode = 'r'
        mode += 'b'
        self._file = open(path, mode=mode)  # pylint: disable=consider-using-with

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._file.close()

    def close(self):
        self._file.close()

    def read(self, numbytes=None):
        bytestring = self._file.read(numbytes)
        return bytestring.decode('utf-8', 'ignore')

    def readBytes(self, numbytes=None):
        return self._file.read(numbytes)

    def seek(self, seekBytes, iWhence=os.SEEK_SET):
        return self._file.seek(seekBytes, iWhence)

    def size(self):
        current_position = self.tell()
        self.seek(0, os.SEEK_END)
        size = self.tell()
        self.seek(current_position)
        return size

    def tell(self):
        return self._file.tell()

    def write(self, buffer):
        try:
            self._file.write(buffer)
            return True
        except (IOError, OSError, TypeError, ValueError):
            return False


def Stat(path):
    ''' A reimplementation of the xbmcvfs Stat() function '''

    class stat:  # pylint: disable=too-few-public-methods
        ''' A reimplementation of the xbmcvfs stat class '''

        def __init__(self, path):
            ''' The constructor xbmcvfs stat class '''
            self._stat = os.stat(path)

        def st_mtime(self):
            ''' The xbmcvfs stat class st_mtime method '''
            return self._stat.st_mtime

    return stat(path)


def delete(path):
    ''' A reimplementation of the xbmcvfs delete() function '''
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def exists(path):
    ''' A reimplementation of the xbmcvfs exists() function '''
    return os.path.exists(path)


def listdir(path):
    ''' A reimplementation of the xbmcvfs listdir() function '''
    files = []
    dirs = []
    for filename in os.listdir(path):
        if os.path.isfile(filename):
            files.append(filename)
        if os.path.isdir(filename):
            dirs.append(filename)
    return dirs, files


def mkdir(path):
    ''' A reimplementation of the xbmcvfs mkdir() function '''
    try:
        os.mkdir(path)
        return True
    except OSError:
        return False


def mkdirs(path):
    ''' A reimplementation of the xbmcvfs mkdirs() function '''
    try:
        os.makedirs(path)
        return True
    except OSError:
        return False


def rmdir(path, force=False):
    ''' A reimplementation of the xbmcvfs rmdir() function '''
    try:
        if force:
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                for filename in filenames:
                    os.remove(os.path.join(dirpath, filename))
                for dirname in dirnames:
                    os.rmdir(os.path.join(dirpath, dirname))
        os.rmdir(path)
        return True
    except OSError:
        return False


if __KODI_MATRIX__:
    def translatePath(path):
        ''' A stub implementation of the xbmcvfs translatePath() function '''
        if path.startswith('special://home'):
            path = path.replace('special://home', os.path.join(os.getcwd(), 'tests'))
        elif path.startswith('special://masterprofile'):
            path = path.replace('special://masterprofile', os.path.join(os.getcwd(), 'tests/userdata'))
        elif path.startswith('special://profile'):
            path = path.replace('special://profile', os.path.join(os.getcwd(), 'tests/userdata'))
        elif path.startswith('special://userdata'):
            path = path.replace('special://userdata', os.path.join(os.getcwd(), 'tests/userdata'))
        return os.path.normpath(path)

    def makeLegalFilename(path):
        ''' A stub implementation of the xbmcvfs makeLegalFilename() function '''
        return os.path.normpath(path)
