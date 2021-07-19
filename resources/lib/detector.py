# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import json
import operator
import os.path
import timeit
from PIL import Image
import xbmc
import constants
import file_utils
import utils


# Create directory where all stored hashes will be saved
SAVE_PATH = os.path.join(
    file_utils.translate_path(
        'special://profile/addon_data/{0}'.format(utils.get_addon_id())
    ),
    'detector',
    ''
)
file_utils.create_directory(SAVE_PATH)


class UpNextHashStore(object):  # pylint: disable=useless-object-inheritance
    """Class to store/save/load hashes used by UpNextDetector"""

    __slots__ = (
        'version',
        'hash_size',
        'seasonid',
        'episode',
        'data',
        'timestamps'
    )

    def __init__(self, **kwargs):
        self.version = kwargs.get('version', '0.1')
        self.hash_size = kwargs.get('hash_size', (8, 8))
        self.seasonid = kwargs.get('seasonid', '')
        self.episode = kwargs.get('episode', constants.UNKNOWN_DATA)
        self.data = kwargs.get('data', {})
        self.timestamps = kwargs.get('timestamps', {})

    @staticmethod
    def int_to_hash(val, hash_size):
        return tuple([  # pylint: disable=consider-using-generator
            1 if bit_val == "1" else 0
            for bit_val in bin(val)[2:].zfill(hash_size)
        ])

    @staticmethod
    def hash_to_int(image_hash):
        return sum(
            bit_val << i
            for i, bit_val in enumerate(reversed(image_hash))
        )

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def is_valid(self, seasonid=None, episode=None):
        # Non-episodic video is being played
        if not self.seasonid or self.episode == constants.UNKNOWN_DATA:
            return False

        # New episode is being played, invalidate old hashes
        if (seasonid is not None and self.seasonid != seasonid
                or episode is not None and self.episode != episode):
            return False

        return True

    def invalidate(self):
        self.seasonid = ''
        self.episode = constants.UNKNOWN_DATA

    def load(self, identifier):
        filename = file_utils.make_legal_filename(identifier, suffix='.json')
        target = os.path.join(SAVE_PATH, filename)
        try:
            with open(target, mode='r') as target_file:
                hashes = json.load(target_file)
        except (IOError, OSError, TypeError, ValueError):
            self.log('Could not load stored hashes from {0}'.format(target))
            return False

        if not hashes:
            return False

        self.version = hashes.get('version', self.version)
        self.hash_size = hashes.get('hash_size', self.hash_size)
        if 'data' in hashes:
            hash_size = self.hash_size[0] * self.hash_size[1]
            self.data = {
                tuple([utils.get_int(i) for i in key[1:-1].split(', ')]):  # pylint: disable=consider-using-generator
                self.int_to_hash(hashes['data'][key], hash_size)
                for key in hashes['data']
            }
        if 'timestamps' in hashes:
            self.timestamps = {
                utils.get_int(episode): hashes['timestamps'][episode]
                for episode in hashes['timestamps']
            }

        self.log('Hashes loaded from {0}'.format(target))
        return True

    def save(self, identifier):
        output = {
            'version': self.version,
            'hash_size': self.hash_size,
            'data': {
                str(hash_index): self.hash_to_int(self.data[hash_index])
                for hash_index in self.data
            },
            'timestamps': self.timestamps
        }

        filename = file_utils.make_legal_filename(identifier, suffix='.json')
        target = os.path.join(SAVE_PATH, filename)
        try:
            with open(target, mode='w') as target_file:
                json.dump(output, target_file, indent=4)
                self.log('Hashes saved to {0}'.format(target))
        except (IOError, OSError, TypeError, ValueError):
            self.log('Error: Could not save hashes to {0}'.format(target),
                     utils.LOGWARNING)
        return output


class UpNextDetector(object):  # pylint: disable=useless-object-inheritance
    """Detector class used to detect end credits in playing video"""

    __slots__ = (
        # Instances
        'capturer',
        'hashes',
        'past_hashes',
        'monitor',
        'player',
        'state',
        'thread',
        # Settings
        'match_number',
        'mismatch_number',
        'significance_level',
        # Variables
        'capture_size',
        'capture_ar',
        'hash_index',
        'match_counts',
        # Signals
        'running',
        'sigstop',
        'sigterm'
    )

    def __init__(self, monitor, player, state):
        self.log('Init')

        self.capturer = xbmc.RenderCapture()
        self.monitor = monitor
        self.player = player
        self.state = state
        self.thread = None

        self.match_counts = {
            'hits': 0,
            'misses': 0
        }
        self._init_hashes()

        self.running = False
        self.sigstop = False
        self.sigterm = False

    @staticmethod
    def _calc_median(vals):
        """Method to calculate median value of a list of values by sorting and
            indexing the list"""

        num_vals = len(vals)
        pivot = num_vals // 2
        vals = sorted(vals)
        if num_vals % 2:
            return vals[pivot]
        return (vals[pivot] + vals[pivot - 1]) / 2

    @staticmethod
    def _calc_significance(vals):
        return 100 * sum(vals) / len(vals)

    @staticmethod
    def _calc_similarity(hash1, hash2):
        """Method to compare the similarity between two image hashes"""

        # Check that hashes are not empty and that dimensions are equal
        if not hash1 or not hash2:
            return 0
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return 0

        # Check whether each pixel is equal
        bit_compare = sum(map(operator.eq, hash1, hash2))
        # Evaluate similarity as a percentage of all pixels in the hash
        return 100 * bit_compare / num_pixels

    @staticmethod
    def _capture_resolution(max_size=None):
        """Method to detect playing video resolution and aspect ratio and
           return a scaled down resolution tuple and aspect ratio for use in
           capturing the video frame buffer at a specific size/resolution"""

        aspect_ratio = float(xbmc.getInfoLabel('Player.Process(VideoDAR)'))

        # Capturing render buffer at higher resolution captures more detail
        # depending on Kodi scaling function used, but slows down processing.
        # Limit captured data to max_size (in kB)
        if max_size:
            max_size = max_size * 8 * 1024
            height = int((max_size / aspect_ratio) ** 0.5)
            width = int(height * aspect_ratio)
        else:
            width = xbmc.getInfoLabel('Player.Process(VideoWidth)')
            width = int(width.replace(',', ''))
            height = xbmc.getInfoLabel('Player.Process(VideoHeight)')
            height = int(height.replace(',', ''))

        return (width, height), aspect_ratio

    @staticmethod
    def _generate_initial_hash(hash_size):
        return (
            [0] * hash_size[0]
            + (
                (
                    [0] * (4 * hash_size[0] // 16)
                    + [1] * (hash_size[0] - 2 * (4 * hash_size[0] // 16))
                    + [0] * (4 * hash_size[0] // 16)
                )
                + (
                    [0] * (6 * hash_size[0] // 16)
                    + [1] * (hash_size[0] - 2 * (6 * hash_size[0] // 16))
                    + [0] * (6 * hash_size[0] // 16)
                )
            ) * ((hash_size[1] - 2) // 2)
            + [0] * hash_size[0]
        )

    @staticmethod
    def _pre_process_image(image, input_size, output_size):
        # Convert captured image data from BGRA to RGBA
        image[0::4], image[2::4] = image[2::4], image[0::4]
        # Convert to greyscale to reduce size of data by a factor of 4
        image = Image.frombuffer(
            'RGBA', input_size, image, 'raw', 'RGBA', 0, 1
        ).convert('L')
        # Resize to reduce number of pixels processed for hashing
        if output_size != input_size:
            image = image.resize(output_size, resample=Image.BOX)

        return image

    @classmethod
    def _calc_image_hash(cls, image):
        # Transform image to show absolute deviation from median pixel luma
        median_pixel = cls._calc_median(image.getdata())
        image_hash = image.point(
            [abs(i - median_pixel) for i in range(256)]
        )

        # Calculate median absolute deviation from the median to represent
        # significant pixels and use transformed image as the hash of the
        # current video frame
        median_pixel = cls._calc_median(image_hash.getdata())
        image_hash = image_hash.point(
            [i > median_pixel for i in range(256)]
        )
        image_hash = tuple(image_hash.getdata())

        return image_hash

    @classmethod
    def _print_hash(cls, hash1, hash2, size=None, prefix=None):
        """Method to print two image hashes, side by side, to the Kodi log"""

        if not hash1 or not hash2:
            return
        num_pixels = len(hash1)
        if num_pixels != len(hash2):
            return

        if not size:
            size = int(num_pixels ** 0.5)
            size = (size, size)

        cls.log('\n\t\t\t'.join(
            [prefix if prefix else '-' * (7 + 4 * size[0])]
            + ['{0:>3} |{1}|{2}|'.format(
                row,
                ' '.join(
                    ['*' if bit else ' ' for bit in hash1[row:row + size[0]]]
                ),
                ' '.join(
                    ['*' if bit else ' ' for bit in hash2[row:row + size[0]]]
                )
            ) for row in range(0, num_pixels, size[0])]
        ))

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def _check_similarity(self, image_hash):
        stats = {
            'is_match': False,
            'possible_match': False,
            # Similarity to representative end credits hash
            'credits': 0,
            # Similarity to previous frame hash
            'previous': 0,
            # Significance level - areas of significant deviation in hash
            'significance': 0,
            # Similarity to hash from other episodes
            'episodes': 0
        }

        # Calculate similarity between current hash and representative hash
        stats['credits'] = self._calc_similarity(
            self.hashes.data.get(self.hash_index['credits']),
            image_hash
        )
        # Match if current hash (loosely) matches representative hash
        if stats['credits'] >= self.state.detect_level - 10:
            stats['is_match'] = True
        # Unless debugging, return if match found, otherwise continue checking
        if stats['is_match'] and not self.state.detector_debug:
            self._hash_match_hit()
            return stats

        # Calculate similarity between current hash and previous hash
        stats['previous'] = self._calc_similarity(
            self.hashes.data.get(self.hash_index['previous']),
            image_hash
        )
        # Calculate percentage of significant pixels
        stats['significance'] = self._calc_significance(image_hash)
        # Match if current hash matches previous hash and has few significant
        # regions of deviation
        if stats['previous'] >= self.state.detect_level:
            stats['possible_match'] = True
            stats['is_match'] = (
                stats['significance'] <= self.significance_level
            )
        # Unless debugging, return if match found, otherwise continue checking
        if stats['is_match'] and not self.state.detector_debug:
            self._hash_match_hit()
            return stats

        # Get all previous hash indexes for episodes other than the current
        # episode and where the hash timestamps are approximately equal (+/- an
        # index_offset)
        episode_idx = self.hash_index['current'][1]
        # Offset equal to the number of matches required for detection
        index_offset = self.match_number
        min_time_idx = self.hash_index['current'][0] - index_offset
        max_time_idx = self.hash_index['current'][0] + index_offset
        old_hash_indexes = [
            idx for idx in self.past_hashes.data
            if idx[1] != episode_idx
            and idx[0] >= min_time_idx
            and idx[0] <= max_time_idx
        ]
        old_hash_index = None
        for old_hash_index in old_hash_indexes:
            stats['episodes'] = self._calc_similarity(
                self.past_hashes.data[old_hash_index],
                image_hash
            )
            # Match if current hash matches other episode hashes
            if stats['episodes'] >= self.state.detect_level:
                stats['is_match'] = True
                break
        self.hash_index['episodes'] = old_hash_index

        # Increment the number of matches
        if stats['is_match']:
            self._hash_match_hit()
        # Otherwise increment number of mismatches
        elif not stats['possible_match']:
            self._hash_match_miss()

        return stats

    def _hash_match_hit(self):
        self.match_counts['hits'] += 1
        self.match_counts['misses'] = 0
        self.match_counts['detected'] = (
            self.match_counts['hits'] >= self.match_number
        )

        if self.credits_detected():
            self.log('Credits detected')
            self.sigstop = self.running

    def _hash_match_miss(self):
        self.match_counts['misses'] += 1

        if self.match_counts['misses'] >= self.mismatch_number:
            self._hash_match_reset()

    def _hash_match_reset(self):
        self.match_counts['hits'] = 0
        self.match_counts['misses'] = 0
        self.match_counts['detected'] = False

    def _init_hashes(self):
        # Limit captured data to 16 kB
        self.capture_size, self.capture_ar = self._capture_resolution(
            max_size=16
        )

        self.hash_index = {
            # Current hash index
            'current': (0, 0),
            # Previous hash index
            'previous': None,
            # Representative end credits hash index
            'credits': (0, 0),
            # Other episodes hash index
            'episodes': None,
            # Detected end credits timestamp from end of file
            'detected_at': None
        }

        # Hash size as (width, height)
        hash_size = [8 * self.capture_ar, 8]
        # Round down width to multiple of 2
        hash_size[0] = int(hash_size[0] - hash_size[0] % 2)
        # Hashes for currently playing episode
        self.hashes = UpNextHashStore(
            version='0.1',
            hash_size=hash_size,
            seasonid=self.state.get_season_identifier(),
            episode=utils.get_int(self.state.get_episode()),
            # Representative hash of centred end credits text on a dark
            # background stored as first hash
            data={
                self.hash_index['credits']: self._generate_initial_hash(
                    hash_size
                )
            },
            timestamps={}
        )

        # Calculated maximum allowable significant level
        # self.significance_level = 0.90 * self.calc_significance(
        #    self.hashes.data[self.hash_index['credits']]
        # )
        self.significance_level = 25

        # Hashes from previously played episodes
        self.past_hashes = UpNextHashStore(hash_size=hash_size)
        if self.hashes.is_valid():
            self.past_hashes.load(self.hashes.seasonid)

        # Number of consecutive frame matches required for a positive detection
        self.match_number = 5
        # Number of consecutive frame mismatches required to reset match count
        # Set to 3 to account for bad frame capture
        self.mismatch_number = 3
        self._hash_match_reset()

    def _run(self):
        """Detection loop captures Kodi render buffer every 1s to create an
           image hash. Hash is compared to the previous hash to determine
           whether current frame of video is similar to the previous frame.

           Hash is also compared to hashes calculated from previously played
           episodes to detect common sequence of frames (i.e. credits).

           A consecutive number of matching frames must be detected to confirm
           that end credits are playing."""

        self.log('Started')
        self.running = True

        if self.state.detector_debug:
            profiler = utils.Profiler()

        play_time = 0
        while not (self.monitor.abortRequested()
                   or self.sigterm or self.sigstop):
            loop_start_time = timeit.default_timer()

            with self.player as check_fail:
                play_time = self.player.getTime()
                total_time = self.player.getTotalTime()
                self.hash_index['current'] = (
                    int(total_time - play_time),
                    self.hashes.episode
                )
                # Only capture if playing at normal speed
                # check_fail = self.player.get_speed() != 1
                check_fail = False
            if check_fail:
                self.log('No file is playing')
                break

            self.capturer.capture(*self.capture_size)
            image = self.capturer.getImage()

            # Capture failed or was skipped, re-initialise RenderCapture
            if not image or image[-1] != 255:
                continue

            # Convert captured video frame from a nominal default 484x272 BGRA
            # image to a 14x8 greyscale image, depending on video aspect ratio
            image = self._pre_process_image(
                image, self.capture_size, self.hashes.hash_size
            )

            # Generate median absolute deviation from median hash
            image_hash = self._calc_image_hash(image)

            # Check if current hash matches with previous hash, typical end
            # credits hash, or other episode hashes
            stats = self._check_similarity(image_hash)

            if self.state.detector_debug:
                self.log('Match: {0[hits]}/{1}, Miss: {0[misses]}/{2}'.format(
                    self.match_counts, self.match_number, self.mismatch_number
                ))

                self._print_hash(
                    self.hashes.data.get(self.hash_index['credits']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to typical credits'
                    ).format(stats['credits'])
                )

                self._print_hash(
                    self.hashes.data.get(self.hash_index['previous']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to previous frame'
                        ' with {1:2.1f}% significant pixels'
                    ).format(stats['previous'], stats['significance'])
                )

                self._print_hash(
                    self.past_hashes.data.get(self.hash_index['episodes']),
                    image_hash,
                    self.hashes.hash_size,
                    (
                        'Hash compare: {0:2.1f}% similar to other episodes'
                    ).format(stats['episodes'])
                )

                self.log(profiler.get_stats())

            # Store current hash for comparison with next video frame
            self.hashes.data[self.hash_index['current']] = image_hash
            self.hash_index['previous'] = self.hash_index['current']

            # Wait until total loop time of 1s has elapsed
            self.monitor.waitForAbort(
                max(0.1, 1 - timeit.default_timer() + loop_start_time)
            )

        self.update_timestamp(play_time, total_time)

        # Reset thread signals
        self.log('Stopped')
        self.running = False
        self.sigstop = False
        self.sigterm = False

    def is_alive(self):
        return self.running

    def cancel(self):
        # Dummy method to match threading/timer object method
        pass

    def credits_detected(self):
        # Ignore invalidated hash data
        if not self.hashes.is_valid():
            return False

        return self.match_counts['detected']

    def start(self, restart=False, reset=False):
        """Method to run actual detection test loop in a separate thread"""

        if restart or self.running:
            self.stop()
        if reset:
            self._hash_match_reset()
        # Reset detector data if episode has changed
        if not self.hashes.is_valid(
                self.state.get_season_identifier(),
                utils.get_int(self.state.get_episode())
        ):
            self._init_hashes()

        # If a previously detected timestamp exists then use it
        stored_timestamp = self.past_hashes.timestamps.get(self.hashes.episode)
        if stored_timestamp and not reset:
            self.log('Stored credits timestamp found')
            self.state.set_popup_time(detected_time=stored_timestamp)

        # Otherwise run the detector in a new thread
        else:
            self.thread = utils.run_threaded(self._run)

    def stop(self, terminate=False):
        # Set terminate or stop signals if detector is running
        if terminate:
            self.sigterm = self.running
        else:
            self.sigstop = self.running

        # Exit if detector thread has not been created
        if not self.thread:
            return

        # Wait for thread to complete
        if self.running:
            self.thread.join()

        # Free references/resources
        del self.thread
        self.thread = None
        if terminate:
            # Invalidate collected hashes if not needed for later use
            self.hashes.invalidate()
            # Delete reference to instances if detector will not be restarted
            del self.capturer
            self.capturer = None
            del self.monitor
            self.monitor = None
            del self.player
            self.player = None
            del self.state
            self.state = None

    def store_data(self):
        # Only store data for videos that are grouped by season (i.e. same show
        # title, same season number)
        if not self.hashes.is_valid():
            return

        self.past_hashes.hash_size = self.hashes.hash_size
        # If credit were detected only store the previous 5s worth of hashes to
        # reduce false positives when comparing to other episodes
        if self.match_counts['detected']:
            detect_offset = self.hash_index['detected_at'] + self.match_number
            self.past_hashes.data.update({
                hash_index: self.hashes.data[hash_index]
                for hash_index in self.hashes.data
                if hash_index[0] <= detect_offset
            })
            self.past_hashes.timestamps.update(self.hashes.timestamps)
        # Otherwise store all hashes for comparison with other episodes
        else:
            self.past_hashes.data.update(self.hashes.data)

        self.past_hashes.save(self.hashes.seasonid)

    def update_timestamp(self, play_time, total_time):
        if not self.credits_detected():
            return

        self.hash_index['detected_at'] = self.hash_index['current'][0]
        self.hashes.timestamps[self.hashes.episode] = play_time
        self.state.set_popup_time(
            total_time=total_time,
            detected_time=play_time
        )

        utils.event('upnext_trigger')
