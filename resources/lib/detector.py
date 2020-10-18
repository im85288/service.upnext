# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import operator
import threading
import timeit
from PIL import Image
import xbmc
import player
import utils


class Detector(object):  # pylint: disable=useless-object-inheritance
    __slots__ = (
        # Instances
        'detector',
        'player',
        'capturer',
        # Settings
        'detect_level',
        'detect_period',
        'debug_output',
        # Variables
        'hash_size',
        'num_pixels',
        'hashes',
        'capture_size',
        'match_count',
        'matches',
        'hashes',
        # Signals
        'running',
        'sigterm'
    )

    def __init__(self):
        self.detector = None
        self.player = player.UpNextPlayer()
        self.capturer = xbmc.RenderCapture()

        self.detect_level = utils.get_setting_int('detectLevel') / 100
        self.detect_period = utils.get_setting_int('detectPeriod')
        self.debug_output = False

        self.hash_size = (16, 16)
        self.num_pixels = self.hash_size[0] * self.hash_size[1]
        self.hashes = [None, None]
        self.capture_size = self.capture_resolution()
        self.match_count = self.detect_period // 10
        self.matches = 0

        self.running = False
        self.sigterm = False

        self.capturer.capture(*self.capture_size)
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
        width = int(xbmc.getInfoLabel('System.ScreenWidth')) // 4
        height = int(xbmc.getInfoLabel('System.ScreenHeight')) // 4
        # width = 16
        # height = 16
        return width, height

    @classmethod
    def print_hash(cls, hash_1, hash_2, size=None, num_pixels=None):
        if not num_pixels:
            num_pixels = len(hash_1)
        if num_pixels != len(hash_1):
            return
        if not size:
            size = int(num_pixels ** 0.5)
            size = (size, size)

        for row in range(0, num_pixels, size[0]):
            cls.log('{0:>3} |{1}|{2}|'.format(
                row,
                ' '.join(
                    ['*' if bit else ' ' for bit in hash_1[row:row + size[1]]]
                ),
                ' '.join(
                    ['*' if bit else ' ' for bit in hash_2[row:row + size[1]]]
                )
            ), 2)

    @classmethod
    def calc_median(cls, vals, num_vals=None):
        if not num_vals:
            num_vals = len(vals)

        pivot = int(num_vals / 2)
        if num_vals % 2:
            return sorted(vals)[pivot]
        else:
            return sum(sorted(vals)[pivot - 1:pivot])

    @classmethod
    def calc_median_hash(cls, pixels, num_pixels=None):
        if not num_pixels:
            num_pixels = len(pixels)

        med_pixel = cls.calc_median(pixels, num_vals=num_pixels)
        return tuple(
            int(pixel > med_pixel)
            for pixel in pixels
        )

    def detected(self):
        self.log('{0}/{1} matches'.format(self.matches, self.match_count), 2)
        return self.matches >= self.match_count

    def reset(self):
        self.matches = 0
        self.match_count = self.detect_period // 10

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
                self.match_count = max(3, self.match_count - 1)
            if not raw:
                continue

            now = timeit.default_timer()
            # Convert from BGRA to RGBA
            raw[0::4], raw[2::4] = raw[2::4], raw[0::4]
            image = Image.frombuffer(
                'RGBA', self.capture_size, raw, 'raw', 'RGBA', 0, 1
            )
            image = image.convert('L')
            image = image.resize(self.hash_size, resample=Image.BOX)
            image_hash = self.calc_median_hash(
                image.getdata(),
                self.num_pixels
            )

            del self.hashes[0]
            self.hashes.append(image_hash)

            similarity = self.calc_similarity(
                self.hashes[0],
                self.hashes[1]
            )
            delta = timeit.default_timer() - now

            if similarity >= self.detect_level:
                self.matches += 1
            else:
                self.matches = 0

            if self.debug_output and similarity is not None:
                self.print_hash(
                    self.hashes[0],
                    self.hashes[1],
                    self.hash_size,
                    self.num_pixels
                )
                self.log('Hash compare:  {0:1.2f} in {1:1.4f}s'.format(
                    similarity,
                    delta
                ), 2)

            monitor.waitForAbort(1)

        del self.player
        del monitor

        self.running = False
        self.sigterm = False
