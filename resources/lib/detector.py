# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import operator
import threading
from PIL import Image, ImageStat
import xbmc
import player
import utils


class Detector:

    def __init__(self, test_mode=None):
        self.hash_size = (16, 16)
        self.num_pixels = self.hash_size[0] * self.hash_size[1]
        self.capture_size = self.capture_resolution()

        self.capturer = xbmc.RenderCapture()
        self.capturer.capture(*self.capture_size)

        if not test_mode:
            self.hashes = [None, None]
            self.detect_level = utils.get_setting_int('detectLevel') / 100
            self.detect_period = utils.get_setting_int('detectPeriod')
            self.detect_count = utils.get_setting_int('detectCount')
            self.match_count = self.detect_count
            self.matches = 0
            self.player = player.UpNextPlayer()

        self.detector = None
        self.running = False
        self.sigterm = False
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    @classmethod
    def calc_similarity(cls, hash1, hash2, compare_func=None):
        if not hash1 or not hash2:
            return None
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return None

        if not compare_func:
            compare_func = operator.eq
        bit_compare = sum(map(compare_func, hash1, hash2))
        similarity = bit_compare / num_pixels
        return similarity

    @classmethod
    def capture_resolution(cls):
        # width = int(xbmc.getInfoLabel('System.ScreenWidth')) // 4
        # height = int(xbmc.getInfoLabel('System.ScreenHeight')) // 4
        width = 16
        height = 16
        return width, height

    def detected(self):
        self.log('{0}/{1} matches'.format(self.matches, self.match_count), 2)
        return self.matches >= self.match_count

    def reset(self):
        self.matches = 0

    def run(self):
        self.detector = threading.Thread(target=self.test)
        # Daemon threads may not work in Kodi, but enable it anyway
        self.detector.daemon = True
        self.detector.start()

    def stop(self):
        self.sigterm = True

    def test(self):
        if self.running:
            return
        self.running = True

        detect_period = 10
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.sigterm:
            speed = self.player.get_speed()
            raw = self.capturer.getImage() if speed == 1 else None

            detect_period -= 1
            if not detect_period:
                detect_period = 10
                self.match_count -= 1
                self.match_count = max(3, self.match_count)
            if not raw:
                continue

            # Convert from BGRA to RGBA
            raw[0::4], raw[2::4] = raw[2::4], raw[0::4]
            image = Image.frombuffer(
                'RGBA', self.capture_size, raw, 'raw', 'RGBA', 0, 1
            )
            image = image.convert('L')
            image = image.resize(self.hash_size, resample=Image.BOX)
            threshold = ImageStat.Stat(image).median[0]
            lut = [i >= threshold for i in range(256)]
            image_hash = list(image.point(lut).getdata())

            del self.hashes[0]
            self.hashes.append(image_hash)

            similarity = self.calc_similarity(
                self.hashes[0],
                self.hashes[1]
            )

            if similarity >= self.detect_level:
                self.matches += 1
            else:
                self.matches = 0

            monitor.waitForAbort(1)

        del self.player
        del monitor

        self.running = False
        self.sigterm = False
