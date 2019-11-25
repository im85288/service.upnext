# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

# pylint: disable=invalid-name,missing-docstring

from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from resources.lib import utils

xbmc = __import__('xbmc')
xbmcaddon = __import__('xbmcaddon')
xbmcgui = __import__('xbmcgui')
xbmcvfs = __import__('xbmcvfs')


class TestEncoding(unittest.TestCase):

    # This is a placeholder
    def test_encoding(self):
        data = 'Foobar'

        encoded_data = utils.encode_data(data)
        print('hex encoded data: %r' % encoded_data)
        decoded_data = utils.decode_data(encoded_data)
        print('hex decoded data: %r' % decoded_data)
        self.assertEqual(data, decoded_data)
