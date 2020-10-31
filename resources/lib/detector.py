# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import json
import operator
import threading
import timeit
from PIL import Image
import xbmc
import player
import statichelper
import utils


class HashStore(object):  # pylint: disable=useless-object-inheritance
    def __init__(self, init_data=None, **kwargs):
        if init_data:
            self.load(init_data)
            return

        self.version = kwargs.get('version', '0.1')
        self.hash_size = kwargs.get('hash_size', (16, 16))
        self.data = kwargs.get('data', [])

    def update_default(self):
        new_default = [0] * self.hash_size[0] * self.hash_size[1]
        for image_hash in self.data[1::]:
            for idx, pixel in enumerate(image_hash):
                new_default[idx] += pixel
        self.data[0] = Detector.calc_threshold_hash(new_default, 0.5)

    @classmethod
    def int_to_hash(cls, val):
        return map(int, format(val, 'b'))

    @classmethod
    def hash_to_int(cls, image_hash):
        return int(''.join(map(str, image_hash)), 2)

    def load(self, data):
        data = json.loads(statichelper.to_unicode(data))
        for key, val in data.items():
            if key == 'data':
                val = map(self.int_to_hash, val)
            setattr(self, key, val)

    def save(self):
        output = dict(
            version=self.version,
            hash_size=self.hash_size,
            data=map(self.hash_to_int, self.data)
        )
        json.dumps(str(output))
        return output


class Detector(object):  # pylint: disable=useless-object-inheritance
    __slots__ = (
        # Instances
        'detector',
        'player',
        'capturer',
        # Settings
        'debug',
        'detect_level',
        # Variables
        'capture_size',
        'capture_ar',
        'hashes',
        'match_count',
        'matches',
        # Signals
        'running',
        'sigterm'
    )

    def __init__(self):
        self.detector = None
        self.player = player.UpNextPlayer()
        self.capturer = xbmc.RenderCapture()

        self.debug = utils.get_setting_bool('detectDebugLogging')
        self.detect_level = utils.get_setting_int('detectLevel') / 100

        self.capture_size, self.capture_ar = self.capture_resolution()

        # Hash size as (width, height)
        hash_size = [8 * self.capture_ar, 8]
        # Round down width to multiple of 2
        hash_size[0] = int(hash_size[0] - hash_size[0] % 2)
        self.hashes = HashStore(
            version='0.1',
            hash_size=hash_size,
            # Representative hash of centred end credits text on a dark
            # background stored as first hash
            data=[(
                [0] * (1 + hash_size[0] // 4)
                + [1] * (hash_size[0] - 2 * (1 + hash_size[0] // 4))
                + [0] * (1 + hash_size[0] // 4)
            ) * hash_size[1]]
        )

        self.match_count = 5
        self.matches = 0

        self.running = False
        self.sigterm = False

        self.capturer.capture(*self.capture_size)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    @classmethod
    def all_equal(cls, *args, **kwargs):
        if not args:
            return False
        if len(args) == 1:
            args = tuple(args[0])
        compare_to = kwargs.get('equals', args[0])
        return args.count(compare_to) == len(args)

    @classmethod
    def calc_similarity(
            cls, hash1, hash2,
            function=operator.eq,
            do_zip=False,
            all_pixels=True
    ):
        if not hash1 or not hash2:
            return None
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return None

        if do_zip:
            bit_compare = sum(map(function, zip(hash1, hash2)))
        else:
            bit_compare = sum(map(function, hash1, hash2))

        if all_pixels:
            similarity = bit_compare / num_pixels
        else:
            similarity = bit_compare / sum(map(any, zip(hash1, hash2)))

        return similarity

    @classmethod
    def capture_resolution(cls):
        # Capturing render buffer at higher resolution captures more detail
        # depending on Kodi scaling function used, but slows down processing
        width = int(
            xbmc.getInfoLabel('Player.Process(VideoWidth)').replace(',', '')
        ) // 8
        height = int(
            xbmc.getInfoLabel('Player.Process(VideoHeight)').replace(',', '')
        ) // 8
        aspect_ratio = float(xbmc.getInfoLabel('Player.Process(VideoDAR)'))
        # width = 14
        # height = 8
        return (width, height), aspect_ratio

    @classmethod
    def print_hash(cls, hash_1, hash_2, size=None):
        """Method to print two image hashes, side by side, to the Kodi log"""
        num_pixels = len(hash_1)
        if num_pixels != len(hash_2):
            return
        if not size:
            size = int(num_pixels ** 0.5)
            size = (size, size)

        seperator = '-' * (5 + size[0] + size[0] + size[0] + size[0])
        cls.log(seperator, 2)
        for row in range(0, num_pixels, size[0]):
            cls.log('{0:>3} |{1}|{2}|'.format(
                row,
                ' '.join(
                    ['*' if bit else ' ' for bit in hash_1[row:row + size[0]]]
                ),
                ' '.join(
                    ['*' if bit else ' ' for bit in hash_2[row:row + size[0]]]
                )
            ), 2)
        cls.log(seperator, 2)

    @classmethod
    def calc_quartiles(cls, vals):
        """Method to calculate approximate quartiles for a list of values by
           sorting and indexing the list"""
        num_vals = len(vals)
        pivots = [
            int(num_vals * 0.25),
            int(num_vals * 0.50),
            int(num_vals * 0.75)
        ]
        vals = sorted(vals)
        return tuple(
            [vals[pivot] for pivot in pivots] if num_vals % 2
            else [sum(vals[pivot - 1:pivot + 1]) // 2 for pivot in pivots]
        )

    @classmethod
    def calc_threshold_hash(cls, pixels, threshold=0.5):
        """Method to create a pixel by pixel hash, where significant pixels
           values are greater than threshold (median by default) pixel value"""
        threshold = cls.calc_quartiles(pixels)[
            0 if threshold == 0.25
            else 2 if threshold == 0.75
            else 1
        ]
        return tuple(
            int(pixel > threshold)
            for pixel in pixels
        )

    def detected(self):
        self.log('{0}/{1} matches'.format(self.matches, self.match_count), 2)
        return self.matches >= self.match_count

    def reset(self):
        self.matches = 0
        self.match_count = 5

    def run(self):
        self.detector = threading.Thread(target=self.test)
        # Daemon threads may not work in Kodi, but enable it anyway
        self.detector.daemon = True
        self.detector.start()

    def stop(self):
        self.sigterm = True

    def test(self):
        """Detection test loop captures Kodi render buffer every 1s to create
           an image hash. Hash is compared to the previous hash to determine
           whether current frame of video is similar to the previous frame.

           A consecutive number of matching frames must be detected to confirm
           that end credits are playing."""
        if self.running:
            return
        self.running = True

        mismatch_count = 0
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.sigterm:
            now = self.debug and timeit.default_timer()
            # Only capture if playing at normal speed
            playing = self.player.get_speed() == 1
            raw = self.capturer.getImage(0) if playing or self.debug else None

            # del self.capturer
            # self.capturer = xbmc.RenderCapture()
            # self.capturer.capture(*self.capture_size)

            # Capture failed or was skipped
            if not raw or raw[-1] != 255:
                continue

            # Convert captured image data from BGRA to RGBA
            raw[0::4], raw[2::4] = raw[2::4], raw[0::4]
            image = Image.frombuffer(
                'RGBA', self.capture_size, raw, 'raw', 'RGBA', 0, 1
            )
            # Convert to greyscale and calculate median pixel luma
            image = image.convert('L')
            if self.hashes.hash_size != self.capture_size:
                image = image.resize(self.hashes.hash_size, resample=Image.BOX)

            # Transform image to show absolute deviation from median pixel luma
            quartiles = self.calc_quartiles(image.getdata())
            lut = [abs(i - quartiles[1]) for i in range(256)]
            image_hash_madm = image.point(lut)

            # Calculate median absolute deviation from the median to represent
            # significant deviations
            quartiles = self.calc_quartiles(image_hash_madm.getdata())
            lut = [i > quartiles[1] for i in range(256)]
            image_hash_madm = image_hash_madm.point(lut)

            # Store transformed image as a hash of current video frame
            image_hash_madm = list(image_hash_madm.getdata())
            self.hashes.data.append(image_hash_madm)

            # Calculate similarity between current hash and previous hash
            similarity = self.calc_similarity(
                self.hashes.data[-2], self.hashes.data[-1]
            )
            # Calculate percentage of significant deviations
            default_similarities = (
                sum(self.hashes.data[-1]) / len(self.hashes.data[-1])
            )

            # If current hash matches previous hash and has few significant
            # regions of deviation then increment the number of matches
            if (similarity >= self.detect_level
                    and 0 < default_similarities < 0.2):
                self.matches += 1
                mismatch_count = 0
            # Otherwise increment number of mismatches
            else:
                mismatch_count += 1
            # If 3 mismatches in a row (to account for bad frame capture), then
            # reset match count
            if mismatch_count > 2:
                self.matches = 0
                mismatch_count = 0
                # self.update_default()

            delta = self.debug and timeit.default_timer() - now

            if self.debug:
                self.print_hash(
                    self.hashes.data[-2],
                    self.hashes.data[-1],
                    self.hashes.hash_size
                )
                self.log('Hash compare: {0:1.2f}/{1:1.2f} in {2:1.4f}s'.format(
                    default_similarities,
                    similarity,
                    delta
                ), 2)

            monitor.waitForAbort(1)

        del self.player
        del monitor

        self.running = False
        self.sigterm = False

    def update_default(self):
        if len(self.hashes.data) < 5:
            return
        new_default = [0] * self.hashes.hash_size[0] * self.hashes.hash_size[1]
        for image_hash in self.hashes.data[-5:]:
            for idx, pixel in enumerate(image_hash):
                new_default[idx] += pixel
        self.hashes.data[0] = self.calc_threshold_hash(new_default, 0.5)
