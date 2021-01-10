# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import json
import operator
import os.path
import threading
import timeit
from PIL import Image
import xbmc
import file_utils
import utils


# Create directory where all stored hashes will be saved
SAVE_PATH = os.path.join(
    file_utils.translate_path(
        'special://profile/addon_data/%s' % utils.addon_id()
    ),
    'detector',
    ''
)
file_utils.create_directory(SAVE_PATH)


class HashStore(object):  # pylint: disable=useless-object-inheritance
    def __init__(self, **kwargs):
        self.version = kwargs.get('version', '0.1')
        self.hash_size = kwargs.get('hash_size', (8, 8))
        self.data = kwargs.get('data', {})

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    @classmethod
    def int_to_hash(cls, val):
        return tuple([int(bit_val) for bit_val in format(val, 'b')])

    @classmethod
    def hash_to_int(cls, image_hash):
        return int(''.join(str(bit_val) for bit_val in image_hash), 2)

    def load(self, identifier):
        filename = file_utils.make_legal_filename(identifier, suffix='.json')
        target = os.path.join(SAVE_PATH, filename)
        try:
            with open(target, mode='r') as target_file:
                data = json.load(target_file)
        except (IOError, OSError, TypeError, ValueError):
            self.log('Could not load stored hashes from %s' % target, 2)
            return False

        if not data:
            return False

        for key, val in data.items():
            if key == 'data':
                val = {
                    tuple([int(sub_idx) for sub_idx in idx[1:-1].split(', ')]):
                        self.int_to_hash(hash_val)
                    for idx, hash_val in val.items()
                }
            setattr(self, key, val)
        self.log('Hashes loaded from %s' % target, 2)
        return True

    def save(self, identifier):
        output = dict(
            version=self.version,
            hash_size=self.hash_size,
            data={
                str(idx): self.hash_to_int(hash)
                for idx, hash in self.data.items()
            }
        )

        filename = file_utils.make_legal_filename(identifier, suffix='.json')
        target = os.path.join(SAVE_PATH, filename)
        try:
            with open(target, mode='w') as target_file:
                json.dump(output, target_file, indent=4)
                self.log('Hashes saved to %s' % target, 2)
        except (IOError, OSError, TypeError, ValueError):
            self.log('Error: Could not save hashes to %s' % target, 1)
        return output


class Detector(object):  # pylint: disable=useless-object-inheritance
    """Detector class used to detect end credits in playing video"""
    __slots__ = (
        # Instances
        'capturer',
        'detector',
        'player',
        'state',
        # Settings
        'debug',
        'detect_level',
        'significance_level',
        # Variables
        'capture_size',
        'capture_ar',
        'hashes',
        'past_hashes',
        'hash_index',
        'matches',
        'credits_detected',
        # Signals
        'running',
        'sigstop',
        'sigterm'
    )

    def __init__(self, player, state):
        self.capturer = xbmc.RenderCapture()
        self.detector = None
        self.player = player
        self.state = state

        self.debug = utils.get_setting_bool('detectDebugLogging')
        self.detect_level = utils.get_setting_int('detectLevel')

        self.capture_size, self.capture_ar = self.capture_resolution(
            scale_down=8
        )

        # Hash size as (width, height)
        hash_size = [8 * self.capture_ar, 8]
        # Round down width to multiple of 2
        hash_size[0] = int(hash_size[0] - hash_size[0] % 2)
        self.hashes = HashStore(
            version='0.1',
            hash_size=hash_size,
            # Representative hash of centred end credits text on a dark
            # background stored as first hash
            data={(0, 0): (
                [0] * hash_size[0]
                + (
                    [0] * (1 + hash_size[0] // 4)
                    + [1] * (hash_size[0] - 2 * (1 + hash_size[0] // 4))
                    + [0] * (1 + hash_size[0] // 4)
                ) * (hash_size[1] - 2)
                + [0] * hash_size[0]
            )}
        )
        self.significance_level = self.calc_significance(
            self.hashes.data[(0, 0)]
        )

        self.past_hashes = HashStore(hash_size=hash_size)
        if self.state.season_identifier:
            self.past_hashes.load(self.state.season_identifier)
        self.hash_index = {
            'credits': (0, 0),
            'episodes': (0, 0),
            'previous': (0, 0),
            'current': (0, 0),
            'store': False
        }

        self.matches = 0
        self.credits_detected = False

        self.running = False
        self.sigstop = False
        self.sigterm = False

        self.capturer.capture(*self.capture_size)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

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
        if num_vals % 2:
            return [vals[pivot] for pivot in pivots]
        return [sum(vals[pivot - 1:pivot + 1]) // 2 for pivot in pivots]

    @classmethod
    def calc_similarity(
            cls, hash1, hash2,
            function=operator.eq,
            do_zip=False,
            target='all'
    ):
        """Method to compare the similarity between two image hashes.
           By default checks whether each bit in the first hash is equal to the
           corresponding bit in the second hash"""
        # Check that hashes are not empty and that dimensions are equal
        if not hash1 or not hash2:
            return 0
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return 0

        # Use zip if comparison function requires an iterator as an argument
        if do_zip:
            bit_compare = sum(map(function, zip(hash1, hash2)))
        else:
            bit_compare = sum(map(function, hash1, hash2))

        # Evaluate similarity as a percentage of all pixels in the hash
        if target == 'all':
            similarity = 100 * bit_compare / num_pixels
        # Or similarity as a percentage of all non-zero pixels in both hashes
        elif target == 'both':
            similarity = 100 * bit_compare / sum(map(any, zip(hash1, hash2)))
        # Or similarity as count of matching pixels
        elif target == 'none':
            similarity = bit_compare

        return similarity

    @classmethod
    def calc_significance(cls, vals):
        return 100 * sum(vals) / len(vals)

    @classmethod
    def capture_resolution(cls, scale_down=1):
        """Method to detect playing video resolution and aspect ratio and
           return a scaled down resolution tuple and aspect ratio for use in
           capturing the video frame buffer at a specific size/resolution"""
        # Capturing render buffer at higher resolution captures more detail
        # depending on Kodi scaling function used, but slows down processing
        width = int(
            xbmc.getInfoLabel('Player.Process(VideoWidth)').replace(',', '')
        ) // scale_down
        height = int(
            xbmc.getInfoLabel('Player.Process(VideoHeight)').replace(',', '')
        ) // scale_down
        aspect_ratio = float(xbmc.getInfoLabel('Player.Process(VideoDAR)'))
        # width = 14
        # height = 8
        return (width, height), aspect_ratio

    @classmethod
    def print_hash(cls, hash1, hash2, size=None, prefix=None):
        """Method to print two image hashes, side by side, to the Kodi log"""
        if not hash1 or not hash2:
            return
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return

        if not size:
            size = int(num_pixels ** 0.5)
            size = (size, size)

        msg = prefix if prefix else '-' * (7 + 4 * size[0])
        for row in range(0, num_pixels, size[0]):
            msg += '\n\t\t\t{0:>3} |{1}|{2}|'.format(
                row,
                ' '.join(
                    ['*' if bit else ' ' for bit in hash1[row:row + size[0]]]
                ),
                ' '.join(
                    ['*' if bit else ' ' for bit in hash2[row:row + size[0]]]
                )
            )
        cls.log(msg, 2)

    def check_similarity(self, image_hash, index_offset):
        is_match = False
        stats = {
            'credits': 0,
            'previous': 0,
            'significance': 0,
            'episodes': 0
        }

        # Calculate similarity between current hash and representative hash
        stats['credits'] = self.calc_similarity(
            self.hashes.data.get(self.hash_index['credits']),
            image_hash
        )
        # Match if current hash (loosely) matches representative hash
        if stats['credits'] >= self.detect_level - 10:
            is_match = True
        # Unless debugging, return if match found, otherwise continue checking
        if is_match and not self.debug:
            return is_match, stats

        # Calculate similarity between current hash and previous hash
        stats['previous'] = self.calc_similarity(
            self.hashes.data.get(self.hash_index['previous']),
            image_hash
        )
        # Calculate percentage of significant pixels
        stats['significance'] = self.calc_significance(image_hash)
        # Match if current hash matches previous hash and has few significant
        # regions of deviation
        if (stats['previous'] >= self.detect_level
                and stats['significance'] <= self.significance_level):
            is_match = True
        # Unless debugging, return if match found, otherwise continue checking
        if is_match and not self.debug:
            return is_match, stats

        old_hash_indexes = (
            idx for idx in self.past_hashes.data
            if (self.hash_index['current'][0] - index_offset <= idx[0]
                <= self.hash_index['current'][0] + index_offset)
            and idx[1] != self.hash_index['current'][1]
        )
        old_hash_index = (0, 0)
        for old_hash_index in old_hash_indexes:
            stats['episodes'] = self.calc_similarity(
                self.past_hashes.data.get(old_hash_index),
                image_hash
            )
            if stats['episodes'] >= self.detect_level:
                is_match = True
                break
        self.hash_index['episodes'] = old_hash_index

        return is_match, stats

    def detected(self):
        required_matches = 3
        self.log('{0}/{1} matches'.format(self.matches, required_matches), 2)
        self.credits_detected = self.matches >= required_matches
        return self.credits_detected

    def reset(self):
        self.matches = 0
        self.credits_detected = False

    def run(self):
        """Method to run actual detection test loop in a separate thread"""
        self.detector = threading.Thread(target=self.test)
        # Daemon threads may not work in Kodi, but enable it anyway
        self.detector.daemon = True
        self.detector.start()

    def stop(self, terminate=False):
        # Exit if detector thread has not been created
        if not self.detector:
            return

        # Set terminate or stop signals if detector is running
        if terminate:
            self.sigterm = self.running
        else:
            self.sigstop = self.running

        # Wait for thread to complete
        if self.running:
            self.detector.join()

        # Free resources
        del self.detector
        self.detector = None
        # Delete reference to instances if detector will not be restarted
        if terminate:
            del self.capturer
            self.capturer = None
            del self.player
            self.player = None
            del self.state
            self.state = None

    def test(self):
        """Detection test loop captures Kodi render buffer every 1s to create
           an image hash. Hash is compared to the previous hash to determine
           whether current frame of video is similar to the previous frame.

           Hash is also compared to hashes calculated from previously played
           episodes to detect common sequence of frames (i.e. credits).

           A consecutive number of matching frames must be detected to confirm
           that end credits are playing."""

        # Only run detector if old detector is not running
        if self.running:
            return
        self.log('Started', 2)
        self.running = True

        mismatch_count = 0
        monitor = xbmc.Monitor()
        while (not monitor.abortRequested()
               and not (self.sigterm or self.sigstop)):
            now = self.debug and timeit.default_timer()
            # Only capture if playing at normal speed
            with self.player as check_fail:
                play_time = self.player.getTime()
                self.hash_index['store'] = self.state.detect_time <= play_time
                self.hash_index['current'] = (
                    int(self.player.getTotalTime() - play_time),
                    self.state.episodeid
                )
                check_fail = self.player.get_speed() != 1
            if check_fail:
                self.log('No file is playing', 2)
                break
            image = self.capturer.getImage()

            # Capture failed or was skipped, re-initialise RenderCapture
            if not image or image[-1] != 255:
                del self.capturer
                self.capturer = xbmc.RenderCapture()
                self.capturer.capture(*self.capture_size)
                continue

            # Convert captured image data from BGRA to RGBA
            image[0::4], image[2::4] = image[2::4], image[0::4]
            # Convert to greyscale to reduce size of data by a factor of 4
            image = Image.frombuffer(
                'RGBA', self.capture_size, image, 'raw', 'RGBA', 0, 1
            ).convert('L')
            # Resize to reduce number of pixels processed for hashing
            if self.hashes.hash_size != self.capture_size:
                image = image.resize(self.hashes.hash_size, resample=Image.BOX)

            # Transform image to show absolute deviation from median pixel luma
            median_pixel = self.calc_quartiles(image.getdata())[1]
            image_hash = image.point(
                [abs(i - median_pixel) for i in range(256)]
            )

            # Calculate median absolute deviation from the median to represent
            # significant pixels and use transformed image as the hash of the
            # current video frame
            median_pixel = self.calc_quartiles(image_hash.getdata())[1]
            image_hash = image_hash.point(
                [i > median_pixel for i in range(256)]
            )
            image_hash = tuple(image_hash.getdata())

            # Check if current hash matches with previous hash, typical end
            # credits hash, or other episode hashes
            is_match, stats = self.check_similarity(image_hash, 2)

            if is_match:
                # Then increment the number of matches
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

            if self.debug:
                self.print_hash(
                    self.hashes.data.get(self.hash_index['credits']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to typical credits'
                    ).format(stats['credits'])
                )

                self.print_hash(
                    self.hashes.data.get(self.hash_index['previous']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to previous frame'
                        ' with {1:2.1f}% significant pixels'
                    ).format(stats['previous'], stats['significance'])
                )

                self.print_hash(
                    self.past_hashes.data.get(self.hash_index['episodes']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to other episodes'
                    ).format(stats['episodes'])
                )

                self.log((
                    'Hash compare: completed in {0:1.4f}s'
                ).format(timeit.default_timer() - now), 2)

            # Store current hash for comparison with next video frame
            # But delete previous hash if not yet required to save it
            if not self.hash_index['store']:
                del self.hashes.data[self.hash_index['previous']]
            self.hashes.data[self.hash_index['current']] = image_hash
            self.hash_index['previous'] = self.hash_index['current']

            monitor.waitForAbort(2)

        # Free resources
        del monitor

        # Reset thread signals
        self.log('Stopped', 2)
        self.running = False
        self.sigstop = False
        self.sigterm = False

    def store_hashes(self):
        if not self.state.season_identifier:
            return
        self.past_hashes.hash_size = self.hashes.hash_size
        self.past_hashes.data.update(self.hashes.data)
        self.past_hashes.save(self.state.season_identifier)
