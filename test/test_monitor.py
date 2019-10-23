# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

# pylint: disable=invalid-name,missing-docstring

from __future__ import absolute_import, division, print_function, unicode_literals
import binascii
import json
import unittest
from resources.lib.api import Api
from resources.lib.monitor import Monitor
from resources.lib.statichelper import to_unicode
from .testdata import episode1

xbmc = __import__('xbmc')
xbmcaddon = __import__('xbmcaddon')
xbmcgui = __import__('xbmcgui')
xbmcvfs = __import__('xbmcvfs')


class TestMonitor(unittest.TestCase):

    addon = xbmcaddon.Addon()
    api = Api()
    monitor = Monitor()

#    def test_run(self):
#        self.monitor.run()

    def test_notification(self):
        self.monitor.onNotification('plugin.video.vrt.nu', 'upnext_data', json.dumps([to_unicode(binascii.hexlify(json.dumps(episode1).encode()))]))
        episode1.update(id='plugin.video.vrt.nu_play_action')
        self.assertEqual(self.api.data, episode1)

    def test__invalid_notification(self):
        self.monitor.onNotification('plugin.video.vrt.nu', 'foo_bar', {})


if __name__ == '__main__':
    unittest.main()
