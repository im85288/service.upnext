# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

# pylint: disable=invalid-name,missing-docstring

from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
import AddonSignals
from resources.lib import utils

xbmc = __import__('xbmc')
xbmcaddon = __import__('xbmcaddon')
xbmcgui = __import__('xbmcgui')
xbmcvfs = __import__('xbmcvfs')


SKIP_TEST_ALL = False
SKIP_TEST_ENCODING = False
SKIP_TEST_JSENCODED = False
SKIP_TEST_FROM_ADDON_SIGNALS = False
SKIP_TEST_TO_ADDON_SIGNALS = False
SKIP_TEST_ADDON_SIGNALS = False


class TestEncoding(unittest.TestCase):

    def test_encoding(self):
        if SKIP_TEST_ALL or SKIP_TEST_ENCODING:
            assert True
            return

        data = 'Fòöbàr'

        hex_encoded_data = '22465c75303066325c7530306636625c75303065307222'
        encoded_data = utils.encode_data(data, 'hex')
        self.assertEqual(encoded_data, hex_encoded_data)
        decoded_data, encoding = utils.decode_data(encoded_data, compat_mode=False)
        self.assertEqual(decoded_data, data)
        self.assertEqual(encoding, 'hex')

        base64_encoded_data = 'IkZcdTAwZjJcdTAwZjZiXHUwMGUwciI='
        encoded_data = utils.encode_data(data, 'base64')
        self.assertEqual(encoded_data, base64_encoded_data)
        decoded_data, encoding = utils.decode_data(encoded_data, compat_mode=False)
        self.assertEqual(decoded_data, data)
        self.assertEqual(encoding, 'base64')

    def test_jsonencoded(self):
        if SKIP_TEST_ALL or SKIP_TEST_JSENCODED:
            assert True
            return

        data = 'Fòöbàr'

        hex_encoded_json = '["22465c75303066325c7530306636625c75303065307222"]'
        encoded_json = '["%s"]' % utils.encode_data(data, 'hex')
        self.assertEqual(encoded_json, hex_encoded_json)
        decoded_data, encoding = utils.decode_data(encoded_json)
        self.assertEqual(decoded_data, data)
        self.assertEqual(encoding, 'hex')

        base64_encoded_json = '["IkZcdTAwZjJcdTAwZjZiXHUwMGUwciI="]'
        encoded_json = '["%s"]' % utils.encode_data(data, 'base64')
        self.assertEqual(encoded_json, base64_encoded_json)
        decoded_data, encoding = utils.decode_data(encoded_json)
        self.assertEqual(decoded_data, data)
        self.assertEqual(encoding, 'base64')

    def test_from_addon_signals(self):
        if SKIP_TEST_ALL or SKIP_TEST_FROM_ADDON_SIGNALS:
            assert True
            return

        data = 'Fòöbàr'

        # pylint: disable=protected-access
        base64_encoded_data = 'IkZcdTAwZjJcdTAwZjZiXHUwMGUwciI='
        encoded_data = AddonSignals._encodeData(data)
        self.assertEqual(encoded_data, base64_encoded_data)
        decoded_data, encoding = utils.decode_data(encoded_data, compat_mode=False)
        self.assertEqual(decoded_data, data)
        self.assertEqual(encoding, 'base64')

    def test_to_addon_signals(self):
        if SKIP_TEST_ALL or SKIP_TEST_TO_ADDON_SIGNALS:
            assert True
            return

        data = 'Fòöbàr'

        base64_encoded_data = 'IkZcdTAwZjJcdTAwZjZiXHUwMGUwciI='
        base64_encoded_json = '["%s"]' % base64_encoded_data
        encoded_data = utils.encode_data(data, 'base64')
        self.assertEqual(encoded_data, base64_encoded_data)

        decoded_data = AddonSignals._decodeData(base64_encoded_json)  # pylint: disable=protected-access
        self.assertEqual(decoded_data, data)

    def test_addon_signals(self):
        if SKIP_TEST_ALL or SKIP_TEST_ADDON_SIGNALS:
            assert True
            return

        data = 'Fòöbàr'
        base64_encoded_data = 'IkZcdTAwZjJcdTAwZjZiXHUwMGUwciI='
        base64_encoded_json = '\\"[\\"%s\\"]\\"' % base64_encoded_data

        encoded_data = AddonSignals._encodeData(data)  # pylint: disable=protected-access
        self.assertEqual(encoded_data, base64_encoded_data)

        base64_encoded_json = '["%s"]' % base64_encoded_data
        decoded_data = AddonSignals._decodeData(base64_encoded_json)  # pylint: disable=protected-access
        self.assertEqual(decoded_data, data)
