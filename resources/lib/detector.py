# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import json
import timeit
import xbmc
from settings import SETTINGS
import constants
import file_utils
import image_utils
import utils
try:
    import queue
except ImportError:
    import Queue as queue


class UpNextHashStore(object):
    """Class to store/save/load hashes used by UpNextDetector"""

    __slots__ = (
        'version',
        'hash_size',
        'seasonid',
        'episode_number',
        'data',
        'timestamps'
    )

    def __init__(self, **kwargs):
        self.version = kwargs.get('version', 0.2)
        self.hash_size = kwargs.get('hash_size', (8, 8))
        self.seasonid = kwargs.get('seasonid', '')
        self.episode_number = kwargs.get(
            'episode_number', constants.UNDEFINED
        )
        self.data = kwargs.get('data', {})
        self.timestamps = kwargs.get('timestamps', {self.episode_number: None})

    @staticmethod
    def int_to_hash(val, hash_size):
        return tuple([  # pylint: disable=consider-using-generator
            1 if bit_val == "1" else 0
            for bit_val in bin(val)[2:].zfill(hash_size)
        ])

    @staticmethod
    def hash_to_int(image_hash):
        return sum(
            (bit_val or 0) << i
            for i, bit_val in enumerate(reversed(image_hash))
        )

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def is_valid(self, seasonid=None, episode_number=None, for_saving=False):
        # Non-episodic video is being played
        if not self.seasonid or self.episode_number == constants.UNDEFINED:
            return False

        # Playlist with no episode details
        if for_saving and self.seasonid.startswith(constants.MIXED_PLAYLIST):
            return False

        # No new episode details, assume current hashes are still valid
        if seasonid is None and episode_number is None:
            return True

        # Current episode matches, current hashes are still valid
        if self.seasonid == seasonid and self.episode_number == episode_number:
            return True

        # New video is being played, invalidate old hashes
        return False

    def invalidate(self):
        self.seasonid = ''
        self.episode_number = constants.UNDEFINED

    def load(self, identifier):
        target = file_utils.get_legal_filename(
            identifier, prefix=SETTINGS.detector_save_path, suffix='.json'
        )
        try:
            with open(target, mode='r', encoding='utf-8') as target_file:
                hashes = json.load(target_file)
        except (IOError, OSError, TypeError, ValueError):
            self.log('Could not load stored hashes from {0}'.format(target))
            return False

        if not hashes:
            return False

        self.version = float(hashes.get('version', self.version))
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
                utils.get_int(episode_number):
                    hashes['timestamps'][episode_number]
                for episode_number in hashes['timestamps']
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
                if hash_index[-1] != constants.UNDEFINED
            },
            'timestamps': self.timestamps
        }

        target = file_utils.get_legal_filename(
            identifier, prefix=SETTINGS.detector_save_path, suffix='.json'
        )
        try:
            with open(target, mode='w', encoding='utf-8') as target_file:
                json.dump(output, target_file, indent=4)
                self.log('Hashes saved to {0}'.format(target))
        except (IOError, OSError, TypeError, ValueError):
            self.log('Could not save hashes to {0}'.format(target),
                     utils.LOGWARNING)
        return output

    def window(self, hash_index,
               size=SETTINGS.detect_matches, all_episodes=False):
        """Get sets of hashes, either from all episodes or only from the first
        and last episodes, where the timestamps are approximately equal (+/- an
        adjustable offset) to the timestamps of the reference hash index"""

        end_time, start_time, episode = hash_index

        if all_episodes:
            excluded_episodes = [constants.UNDEFINED]
            selected_episodes = self.timestamps.keys()
        else:
            excluded_episodes = [constants.UNDEFINED, episode]
            selected_episodes = {min(self.timestamps), max(self.timestamps)}

        # Matching time period from start of file
        min_start_time = start_time - size
        max_start_time = start_time + size
        # Matching time period from end of file
        min_end_time = end_time - size
        max_end_time = end_time + size

        return {
            hash_index: self.data[hash_index]
            for hash_index in self.data
            if hash_index[2] in selected_episodes
            and hash_index[2] not in excluded_episodes
            and (
                min_start_time <= hash_index[1] <= max_start_time
                or min_end_time <= hash_index[0] <= max_end_time
            )
        }


class UpNextDetector(object):
    """Detector class used to detect end credits in playing video"""

    __slots__ = (
        # Instances
        'hashes',
        'past_hashes',
        'player',
        'state',
        # Settings
        'match_number',
        'mismatch_number',
        # Variables
        'capture_interval',
        'hash_index',
        'match_counts',
        # Worker pool
        'queue',
        'workers',
        # Signals
        '_lock',
        '_running',
        '_sigstop',
        '_sigterm'
    )

    def __init__(self, player, state):
        self.log('Init')

        self.player = player
        self.state = state
        self.queue = None
        self.workers = None

        self.match_counts = {
            'hits': 0,
            'misses': 0,
            'detected': False
        }
        self._lock = utils.create_lock()
        self._init_hashes()

        self._running = utils.create_event()
        self._sigstop = utils.create_event()
        self._sigterm = utils.create_event()

    @staticmethod
    def _and(bit1, bit2):
        return 1 if (bit1 and bit2) else 0

    @staticmethod
    def _eq_biased(bit1, bit2):
        return (bit1 == bit2) * (1 if bit2 else 0.5)

    @staticmethod
    def _mul(bit1, bit2):
        return bit1 * bit2

    @staticmethod
    def _xor(bit1, bit2):
        return 1 if ((bit1 or bit2) and (bit2 != bit1 is not None)) else 0

    @staticmethod
    def _generate_initial_hash(hash_width, hash_height, pad_height=0):
        blank_token = (0, )
        pixel_token = (1, )
        border_token = (0, )
        ignore_token = (None, )

        pad_width = (3 * hash_width // 16) - (hash_width // 16)
        pad_width_alt = (2 * hash_width // 16) - (hash_width // 16)

        return (
            border_token * hash_width * pad_height
            + (
                border_token
                + blank_token * 2 * pad_width
                + ignore_token * (hash_width - 4 * pad_width - 2)
                + blank_token * 2 * pad_width
                + border_token
            )
            + ((
                border_token
                + blank_token * pad_width
                + ignore_token * pad_width
                + pixel_token * (hash_width - 4 * pad_width - 2)
                + ignore_token * pad_width
                + blank_token * pad_width
                + border_token
            ) + (
                border_token
                + blank_token * pad_width_alt
                + ignore_token * pad_width_alt
                + pixel_token * (hash_width - 4 * pad_width_alt - 2)
                + ignore_token * pad_width_alt
                + blank_token * pad_width_alt
                + border_token
            )) * ((hash_height - 2 * pad_height - 2) // 2)
            + (
                border_token
                + blank_token * 2 * pad_width
                + ignore_token * (hash_width - 4 * pad_width - 2)
                + blank_token * 2 * pad_width
                + border_token
            )
            + border_token * hash_width * pad_height
        )

    @staticmethod
    def _generate_mask(image_hash):
        fuzzy_value = None
        masked_value = 0

        mask = len(image_hash) / image_hash.count(masked_value)
        fuzzy_mask = 0.25
        min_mask = 0.25

        return tuple(
            mask if bit == masked_value else
            fuzzy_mask if bit == fuzzy_value else
            min_mask
            for bit in image_hash
        )

    @staticmethod
    def _get_video_capture_resolution(max_size=None):
        """Method to return a scaled down capture resolution tuple for use in
           capturing the video frame buffer at a specific size/resolution"""

        width, height, aspect_ratio = UpNextDetector._get_video_resolution()

        # Capturing render buffer at higher resolution captures more detail
        # depending on Kodi scaling function used, but slows down processing.
        # Limit captured data to max_size (in kB)
        if max_size:
            max_size = max_size * 8 * 1024
            height = min(int((max_size / aspect_ratio) ** 0.5), height)
            width = min(int(height * aspect_ratio), width)

        return width, height

    @staticmethod
    def _get_video_resolution():
        """Method to detect playing video resolution and aspect ratio"""

        width = xbmc.getInfoLabel('Player.Process(VideoWidth)')
        width = int(width.replace(',', ''))
        height = xbmc.getInfoLabel('Player.Process(VideoHeight)')
        height = int(height.replace(',', ''))
        aspect_ratio = width / height

        return width, height, aspect_ratio

    @staticmethod
    def _create_hash(image, hash_size, output_file=None):
        image_hash = image_utils.process(
            image,
            queue=[
                [image_utils.resize, hash_size],
                [image_utils.points_of_interest],
                [image_utils.export_data],
            ],
            save_file=output_file
        )

        return image_hash

    @classmethod
    def _create_images(cls, image_data, image_size):
        image = image_utils.process(
            image_data,
            queue=[
                [image_utils.import_data, image_size],
                [image_utils.auto_level, 5, 95, (0.33, None)],
            ],
            save_file='1_image'
        )

        filtered_image = image_utils.process(
            image,
            queue=[
                [image_utils.posterise, 3],
                [image_utils.adaptive_filter, (8, 1, True),
                 image_utils.auto_level, (5, 95, (0.33, None))],
                [image_utils.apply_filter,
                 'UnsharpMask,20,400,64', 'TRIM'],
                [image_utils.apply_filter,
                 'RankFilter,5,50', 'TRIM', None, 'difference'],
                [image_utils.detail_reduce, image, 50],
                [image_utils.apply_filter,
                 'GaussianBlur,5', 'TRIM', None, 'multiply'],
                [image_utils.threshold],
            ],
            save_file='2_filter'
        )

        return image, filtered_image

    @classmethod
    def _hash_fuzz(cls, image_hash, masking_hash, factor=5):
        weights = cls._generate_mask(masking_hash)

        significant_bits = sum(map(cls._mul, image_hash, weights))
        significance = 100 * significant_bits / len(image_hash)
        delta = significance - SETTINGS.detect_significance

        return factor * delta / SETTINGS.detect_significance

    @classmethod
    def _hash_similarity(cls, baseline_hash, image_hash, filtered_hash=None):
        """Method to compare the similarity between image hashes"""

        # Check that hashes are not empty and that dimensions are equal
        if not baseline_hash or not image_hash:
            return 0

        compare_hash = filtered_hash or image_hash

        num_pixels = len(baseline_hash)
        if num_pixels != len(compare_hash):
            return 0

        # Check whether each pixel is equal
        bits_eq = sum(map(cls._eq_biased, baseline_hash, compare_hash))
        bits_xor = map(cls._xor, baseline_hash, compare_hash)
        bits_xor_baseline = sum(map(cls._and, bits_xor, baseline_hash))
        bits_xor_compare = sum(map(cls._and, bits_xor, compare_hash))

        weighted_total = (
            num_pixels
            - baseline_hash.count(None)
            - (min(baseline_hash.count(0), compare_hash.count(0)) / 2)
        )
        bit_compare = bits_eq - bits_xor_baseline - bits_xor_compare

        # Evaluate similarity as a percentage of un-ignored pixels in the hash
        similarity = max(0, 100 * bit_compare / weighted_total)

        if not filtered_hash:
            uncertainty = 0
        elif filtered_hash != image_hash:
            uncertainty = cls._hash_fuzz(image_hash, filtered_hash)
        else:
            uncertainty = cls._hash_fuzz(image_hash, baseline_hash)

        return similarity - uncertainty

    @classmethod
    def _print_hashes(cls, hashes, size, prefix=''):
        """Method to print image hashes, side by side, to the Kodi log"""

        if not hashes:
            return

        num_bits = size[0] * size[1]
        row_length = size[0]

        hashes = [image_hash if image_hash and len(image_hash) == num_bits
                  else (0, ) * num_bits
                  for image_hash in hashes]

        cls.log('\n\t\t\t'.join([
            prefix,
            '{0}|{1}|'.format(
                size,
                '|'.join(str(UpNextHashStore.hash_to_int(image_hash))
                         for image_hash in hashes)
            )
        ] + ['{0:>3}|{1}|'.format(
            row,
            '|'.join(' '.join('+' if bit else '-' if bit is None else ' '
                              for bit in image_hash[row:row + row_length])
                     for image_hash in hashes)
        ) for row in range(0, num_bits, row_length)]))

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def _evaluate_similarity(self, image, filtered_image, hash_size):
        is_match = False
        possible_match = False

        stats = {
            # Similarity to representative end credits hash
            'credits': constants.UNDEFINED,
            # Similarity between detected credits hashes
            'detected': constants.UNDEFINED,
            # Similarity to previous frame hash
            'previous': constants.UNDEFINED,
            # Similarity to hash from other episodes
            'episodes': constants.UNDEFINED
        }

        has_credits, expanded_image = image_utils.process(
            image,
            queue=[
                [image_utils.has_credits, filtered_image]
            ],
            save_file='3_expanded'
        )

        image_hash = self._create_hash(image, hash_size)
        filtered_hash = self._create_hash(filtered_image, hash_size)
        expanded_hash = None

        if has_credits:
            expanded_hash = self._create_hash(expanded_image, hash_size)

            # Calculate similarity between current hash and representative hash
            stats['credits'] = max(self._hash_similarity(
                self.hashes.data.get(self.hash_index['credits_small']),
                image_hash,
                filtered_hash
            ), self._hash_similarity(
                self.hashes.data.get(self.hash_index['credits_large']),
                image_hash,
                filtered_hash
            ), self._hash_similarity(
                self.hashes.data.get(self.hash_index['credits_full']),
                image_hash,
                filtered_hash
            ))

            # Estimate of detection relevance
            stats['detected'] = stats['credits'] * self._hash_similarity(
                expanded_hash, image_hash, filtered_hash
            ) / self._hash_similarity(
                filtered_hash, image_hash, expanded_hash
            )

        # Match if current hash matches representative hash or if current hash
        # is blank
        is_match = (
            not any(image_hash)
            or stats['credits'] >= SETTINGS.detect_level
        )
        # Unless debugging, return if match found, otherwise continue checking
        if is_match and not SETTINGS.detector_debug:
            self._hash_match_hit()
            return stats, (image_hash, filtered_hash, expanded_hash)

        # Calculate similarity between current hash and previous hash
        stats['previous'] = self._hash_similarity(
            self.hashes.data.get(self.hash_index['previous']),
            image_hash
        )
        # Possible match if current hash matches previous hash
        possible_match = stats['previous'] >= SETTINGS.detect_level
        # Match if detection estimate indicates result was relevant
        is_match = is_match or (
            possible_match and
            stats['detected'] >= (
                SETTINGS.detect_level -
                (0.004 * stats['previous'] * stats['credits'])
            )
        )
        # Unless debugging, return if match found, otherwise continue checking
        if is_match and not SETTINGS.detector_debug:
            self._hash_match_hit()
            return stats, (image_hash, filtered_hash, expanded_hash)

        old_hashes = self.past_hashes.window(self.hash_index['current'])
        for self.hash_index['episodes'], old_hash in old_hashes.items():
            stats['episodes'] = self._hash_similarity(
                old_hash,
                image_hash
            )
            # Match if current hash matches other episode hashes
            if stats['episodes'] >= SETTINGS.detect_level:
                is_match = True
                break

        # Increment the number of matches
        if is_match:
            self._hash_match_hit()
        # Otherwise increment number of mismatches
        elif not possible_match:
            self._hash_match_miss()

        return stats, (image_hash, filtered_hash, expanded_hash)

    def _hash_match_hit(self):
        with self._lock:
            self.match_counts['hits'] += 1
            self.match_counts['misses'] = 0
            self.match_counts['detected'] = (
                self.match_counts['hits'] >= self.match_number
            )

    def _hash_match_miss(self):
        with self._lock:
            self.match_counts['misses'] += 1
            if self.match_counts['misses'] < self.mismatch_number:
                return
        self._hash_match_reset()

    def _hash_match_reset(self):
        with self._lock:
            self.match_counts['hits'] = 0
            self.match_counts['misses'] = 0
            self.match_counts['detected'] = False

    def _init_hashes(self):
        # Set minimum capture interval to decrease capture rate
        self.capture_interval = 1

        self.hash_index = {
            # Hash indexes are tuples containing the following data:
            # (time_to_end, time_from_start, episode_number)
            # Current hash
            'current': (0, 0, 0),
            # Previous hash
            'previous': None,
            # Representative end credits hashes
            'credits_small': (0, 0, constants.UNDEFINED),
            'credits_large': (0, 1, constants.UNDEFINED),
            'credits_full': (0, 2, constants.UNDEFINED),
            # Other episodes hash
            'episodes': None,
            # Detected end credits timestamp from end of file
            'detected_at': None
        }

        # Hash size as (width, height)
        hash_size = [8 * self._get_video_resolution()[2], 8]
        # Round down width to multiple of 2
        hash_size[0] = int(hash_size[0] - hash_size[0] % 2)

        # Hashes for currently playing episode
        self.hashes = UpNextHashStore(
            hash_size=hash_size,
            seasonid=self.state.get_season_identifier(),
            episode_number=self.state.get_episode_number(),
            # Representative hash of centred end credits text on a dark
            # background stored as first hash. Masked significance weights
            # stored as second hash.
            data={
                self.hash_index['credits_small']: self._generate_initial_hash(
                    *hash_size,
                    pad_height=(hash_size[1] // 4)
                ),
                self.hash_index['credits_large']: self._generate_initial_hash(
                    *hash_size,
                    pad_height=(hash_size[1] // 8)
                ),
                self.hash_index['credits_full']: self._generate_initial_hash(
                    *hash_size
                ),
            },
        )

        # Hashes from previously played episodes
        self.past_hashes = UpNextHashStore(hash_size=hash_size)
        if SETTINGS.detector_save_path and self.hashes.is_valid():
            self.past_hashes.load(self.hashes.seasonid)

        # Number of consecutive frame matches required for a positive detection
        # Set to 5s of captured frames as default
        self.match_number = int(
            SETTINGS.detect_matches / self.capture_interval
        )
        # Number of consecutive frame mismatches required to reset match count
        # Set to 3 frames to account for bad frame capture
        self.mismatch_number = SETTINGS.detect_mismatches
        self._hash_match_reset()

    def _queue_clear(self):
        if not self.queue:
            return

        with self.queue.mutex:
            self.queue.queue.clear()
            self.queue.all_tasks_done.notify_all()
            self.queue.unfinished_tasks = 0

    def _queue_init(self):
        del self.queue
        self.queue = queue.Queue(maxsize=SETTINGS.detector_threads)

    def _queue_push(self):
        capturer, size = self._queue_pull()

        abort = False
        while not (abort or self._sigterm.is_set() or self._sigstop.is_set()):
            loop_start = timeit.default_timer()

            with self.player as check_fail:
                check_fail = self.player.get_speed() < 1
            if check_fail:
                self.log('Stop capture: nothing playing')
                break

            capturer.capture(*size)
            image_data = capturer.getImage()

            # Capture failed or was skipped, retry with less data
            if not image_data or image_data[-1] != 255:
                self.log('Capture failed using {0}kB data limit'.format(
                    SETTINGS.detector_data_limit
                ), utils.LOGWARNING)
                SETTINGS.detector_data_limit = (
                    SETTINGS.detector_data_limit - 8
                ) or 8

                size = self._get_video_capture_resolution(
                    max_size=SETTINGS.detector_data_limit
                )

                del capturer
                capturer = xbmc.RenderCapture()
                continue

            try:
                self.queue.put(
                    (image_data, size), timeout=self.capture_interval
                )

                loop_time = timeit.default_timer() - loop_start
                if loop_time >= self.capture_interval:
                    raise queue.Full

                abort = utils.wait(self.capture_interval - loop_time)

            except AttributeError:
                self.log('Stop capture: detector stopped')
                break

            except queue.Full:
                self.log('Capture/detection desync', utils.LOGWARNING)
                abort = utils.abort_requested()
                continue

        del capturer
        self._queue_task_done()
        self._queue_clear()

    def _queue_pull(self, timeout=None):
        if not self.queue:
            return None

        return self.queue.get(timeout=timeout)

    def _queue_task_done(self):
        if not self.queue or not self.queue.unfinished_tasks:
            return

        self.queue.task_done()

    @utils.Profiler(enabled=SETTINGS.detector_debug, lazy=True)
    def _worker(self):
        """Detection loop captures Kodi render buffer every 1s to create an
           image hash. Hash is compared to the previous hash to determine
           whether current frame of video is similar to the previous frame.

           Hash is also compared to hashes calculated from previously played
           episodes to detect common sequence of frames (i.e. credits).

           A consecutive number of matching frames must be detected to confirm
           that end credits are playing."""

        while not (self._sigterm.is_set() or self._sigstop.is_set()):
            with self.player as check_fail:
                play_time = self.player.getTime()
                self.hash_index['current'] = (
                    int(self.player.getTotalTime() - play_time),
                    int(play_time),
                    self.hashes.episode_number
                )
                # Only capture if playing at normal speed
                check_fail = self.player.get_speed() < 1
            if check_fail:
                self.log('No file is playing')
                break

            try:
                image_data, size = self._queue_pull(SETTINGS.detector_threads)
                if not isinstance(image_data, bytearray):
                    raise queue.Empty
            except TypeError:
                self.log('Queue empty - exiting')
                break
            except queue.Empty:
                self.log('Queue empty - retry')
                continue

            image, filtered_image = self._create_images(image_data, size)

            # Check if current hash matches with previous hash, typical end
            # credits hash, or other episode hashes
            stats, hashes = self._evaluate_similarity(
                image, filtered_image, self.hashes.hash_size
            )
            image_hash, filtered_hash, expanded_hash = hashes

            if SETTINGS.detector_debug:
                self.log('Match: {0[hits]}/{1}, Miss: {0[misses]}/{2}'.format(
                    self.match_counts, self.match_number, self.mismatch_number
                ))

                self._print_hashes(
                    [filtered_hash,
                     expanded_hash,
                     self.hashes.data.get(self.hash_index['credits_small']),
                     self.hashes.data.get(self.hash_index['credits_large']),
                     self.hashes.data.get(self.hash_index['credits_full'])],
                    size=self.hashes.hash_size,
                    prefix=(
                        '{0:.1f}% similar to typical credits, '
                        '{1:.1f}% similarity in detected credits'
                    ).format(stats['credits'], stats['detected'])
                )

                self._print_hashes(
                    [self.hashes.data.get(self.hash_index['previous']),
                     image_hash,
                     self.past_hashes.data.get(self.hash_index['episodes'])],
                    size=self.hashes.hash_size,
                    prefix=(
                        '{0:.1f}% similar to previous hash, '
                        '{1:.1f}% similar to other episodes'
                    ).format(stats['previous'], stats['episodes'])
                )

            # Store current hash for comparison with next video frame
            self.hashes.data[self.hash_index['current']] = image_hash
            self.hash_index['previous'] = self.hash_index['current']

            # Store timestamps if credits are detected
            self.update_timestamp(play_time)

            self._queue_task_done()

        self._queue_task_done()

    def _worker_release(self):
        if not self.workers or not self.queue:
            return

        for idx, worker in enumerate(self.workers):
            if worker.is_alive():
                try:
                    self.queue.put_nowait(None)
                except queue.Full:
                    pass
                worker.join(SETTINGS.detector_threads * self.capture_interval)

            if worker.is_alive():
                self.log('Worker {0}({1}) is taking too long to stop'.format(
                    idx, worker.ident
                ), utils.LOGWARNING)

    def is_alive(self):
        return self._running.is_set()

    def cancel(self):
        self.stop()

    def credits_detected(self):
        # Ignore invalidated hash data
        if not self.hashes.is_valid():
            return False

        return self.match_counts['detected']

    def reset(self):
        self._hash_match_reset()
        self.hashes.timestamps[self.hashes.episode_number] = None
        self.hash_index['detected_at'] = None

    def start(self, restart=False):
        """Method to run actual detection test loop in a separate thread"""

        if restart or self._running.is_set():
            self.stop()

        # Reset detector data if episode has changed
        if not self.hashes.is_valid(
                self.state.get_season_identifier(),
                self.state.get_episode_number()
        ):
            self._init_hashes()

        # If a previously detected timestamp exists then use it
        stored_timestamp = self.past_hashes.timestamps.get(
            self.hashes.episode_number
        )
        if stored_timestamp and not SETTINGS.detector_debug:
            self.log('Stored credits timestamp found')
            self.state.set_detected_popup_time(stored_timestamp)
            utils.event('upnext_credits_detected')
            return

        # Otherwise run the detector in a new thread
        self.log('Started')

        self._queue_init()
        self.queue.put_nowait([
            xbmc.RenderCapture(),
            self._get_video_capture_resolution(
                max_size=SETTINGS.detector_data_limit
            )
        ])
        self.workers = [utils.run_threaded(self._queue_push)]
        self.workers += [
            utils.run_threaded(
                self._worker,
                delay=(start_delay * self.capture_interval)
            )
            for start_delay in range(SETTINGS.detector_threads - 1)
        ]

        self._running.set()
        self.queue.join()
        self._worker_release()

        self.log('Stopped')
        self._running.clear()
        self._sigstop.clear()
        self._sigterm.clear()

    def stop(self, terminate=False):
        # Set terminate or stop signals if detector is running
        if self._running.is_set():
            if terminate:
                self._sigterm.set()
            else:
                self._sigstop.set()

            self._queue_clear()
            self._worker_release()
            utils.wait(1)

        # Free references/resources
        with self._lock:
            del self.workers
            self.workers = None
            del self.queue
            self.queue = None
            if terminate:
                # Invalidate collected hashes if not needed for later use
                self.hashes.invalidate()
                # Delete reference to instances if not needed for later use
                del self.player
                self.player = None
                del self.state
                self.state = None

    def store_data(self):
        # Only store data for videos that are grouped by season (i.e. same show
        # title, same season number)
        if not self.hashes.is_valid(for_saving=True):
            return

        self.past_hashes.hash_size = self.hashes.hash_size
        self.past_hashes.timestamps.update(self.hashes.timestamps)
        # If credit were detected only store the previous +/- 5s of hashes to
        # reduce false positives when comparing to other episodes
        self.past_hashes.data.update(self.hashes.window(
            self.hash_index['detected_at'], all_episodes=True
        ) if self.match_counts['detected'] else self.hashes.data)

        if SETTINGS.detector_save_path:
            self.past_hashes.save(self.hashes.seasonid)

    def update_timestamp(self, play_time):
        # Timestamp already stored or credits not detected
        if self.hash_index['detected_at'] or not self.credits_detected():
            return

        with self._lock:
            self.log('Credits detected')
            self.hash_index['detected_at'] = self.hash_index['current']
            self.hashes.timestamps[self.hashes.episode_number] = play_time
            self.state.set_detected_popup_time(play_time)
            utils.event('upnext_credits_detected')
