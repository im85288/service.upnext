# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import operator
import threading
import xbmc
import player
import utils


def log(msg, level=2):
    utils.log(msg, name=__name__, level=level)


def calc_similarity(bit_hash1, bit_hash2, compare_func=None):
    if not bit_hash1 or not bit_hash2:
        return None
    num_pixels = len(bit_hash1)
    if num_pixels != len(bit_hash2):
        return None

    if not compare_func:
        compare_func = operator.eq
    bit_compare = sum(map(compare_func, bit_hash1, bit_hash2))
    similarity = bit_compare / num_pixels
    return similarity


def equal_margin(val1, val2, margin=0.5):
    return int(val2 * (1 - margin) <= val1 <= val2 * (1 + margin))


def local_minmax(idx, pixel, pixels, delta, size=None, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels)
    if not size:
        size = int(num_pixels ** 0.5)

    offset = 1 - size
    max_x_position = size - 1
    pixel_hi = pixel + delta
    pixel_lo = pixel - delta

    x_position = idx % size
    left_offset = 1 if x_position else offset
    right_offset = 1 if x_position < max_x_position else offset

    right_idx = idx + right_offset
    left_idx = idx - left_offset

    above_idx = idx - size
    below_idx = (idx + size) - num_pixels

    return int(
        pixels[left_idx] < pixel_lo > pixels[right_idx]
        or pixels[left_idx] > pixel_hi < pixels[right_idx]
        or pixels[above_idx] < pixel_lo > pixels[below_idx]
        or pixels[above_idx] > pixel_hi < pixels[below_idx]
    )


def calc_local_hash(pixels, size=None, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels)
    if not size:
        size = int(num_pixels ** 0.5)

    med_pixel, pivot = calc_median(pixels, num_vals=num_pixels)
    significant_delta = calc_median(
        (abs(pixel - med_pixel) for pixel in pixels),
        pivot=pivot
    )[0] / 4

    return tuple(
        local_minmax(
            idx,
            pixel,
            pixels,
            significant_delta,
            size,
            num_pixels
        )
        for idx, pixel in enumerate(pixels)
    )


def calc_pixel_luma(R, G, B):
    # Approximation of REC. 601 luma coefficients for RGB values scaled
    # from 0-255 to 0-1
    return 0.001173 * R + 0.002302 * G + 0.000447 * B


def convert_greyscale(pixels):
    return tuple(map(
        calc_pixel_luma,
        pixels[2::4],
        pixels[1::4],
        pixels[0::4]
    ))


def calc_average_pixel(pixels, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels)

    return sum(pixels) / num_pixels


def calc_average_hash(pixels, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels)

    avg_pixel = calc_average_pixel(pixels, num_pixels)
    return tuple(
        int(pixel >= avg_pixel)
        for pixel in pixels
    )


def calc_median(vals, num_vals=None, pivot=None):
    if not pivot:
        if not num_vals:
            num_vals = len(vals)
        pivot = int(num_vals / 2)

    return sum(sorted(vals)[pivot - 1:pivot]), pivot


def calc_median_hash(pixels, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels)

    med_pixel = calc_median(pixels, num_vals=num_pixels)[0]
    return tuple(
        int(pixel > med_pixel)
        for pixel in pixels
    )


def calc_diff_hash(pixels_1, pixels_2):
    return tuple(map(
        operator.ge,
        pixels_1,
        pixels_2
    ))


def calc_x_diff_hash(pixels):
    rot_left = pixels[1:] + pixels[:1]
    return calc_diff_hash(pixels, rot_left)


def calc_y_diff_hash(pixels, size=None):
    if not size:
        size = int(len(pixels) ** 0.5)

    flat_transpose = tuple(
        col
        for row in range(size)
        for col in pixels[row::size]
    )
    flat_transpose_rot_up = tuple(
        col
        for row in range(size)
        for col in tuple(pixels[size:] + pixels[:size])[row::size]
    )
    return calc_diff_hash(flat_transpose, flat_transpose_rot_up)


def calc_xy_diff_hash(pixels, size=None):
    if not size:
        size = int(len(pixels) ** 0.5)

    return calc_x_diff_hash(pixels) + calc_y_diff_hash(pixels, size)


def print_hash(pixels_1, pixels_2, size=None, num_pixels=None):
    if not num_pixels:
        num_pixels = len(pixels_1)
    if num_pixels != len(pixels_2):
        return
    if not size:
        size = int(num_pixels ** 0.5)

    for row in range(0, num_pixels, size):
        log('{0:>3} |{1}|{2}|'.format(
            row,
            ' '.join(
                ['*' if pixel else ' ' for pixel in pixels_1[row:row + size]]
            ),
            ' '.join(
                ['*' if pixel else ' ' for pixel in pixels_2[row:row + size]]
            )
        ), 2)


class Detector:

    def __init__(self, method=None):
        self.size = 16
        self.num_pixels = self.size * self.size
        if not method:
            self.hash_method = calc_median_hash

        self.capturer = xbmc.RenderCapture()
        self.capturer.capture(self.size, self.size)

        self.hashes = [None, None]
        self.detect_threshold = utils.get_setting_int('detectThreshold') / 100
        self.detect_count = utils.get_setting_int('detectCount')
        self.similarities = [None] * self.detect_count

        self.show_output = False

        self.player = player.UpNextPlayer()
        self.detector = None
        self.running = False
        self.sigterm = False
        log('Init', 2)

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

        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.sigterm:
            speed = self.player.get_speed()
            raw = self.capturer.getImage() if speed == 1 else None
            monitor.waitForAbort(1)
            if not raw:
                continue

            greyscale = convert_greyscale(raw)
            hash = self.hash_method(greyscale)
            del self.hashes[0]
            self.hashes.append(hash)

            similarity = calc_similarity(
                self.hashes[0],
                self.hashes[1]
            )

            if self.show_output and similarity is not None:
                print_hash(
                    self.hashes[0],
                    self.hashes[1],
                    self.size,
                    self.num_pixels
                )
                log('Hash compare:  {0:1.2f}'.format(similarity), 2)

            del self.similarities[0]
            self.similarities.append(similarity >= self.detect_threshold)

        del self.player
        del monitor

        self.running = False
        self.sigterm = False

    def detected(self):
        if None in self.similarities:
            return False
        return sum(self.similarities) == self.detect_count

    def reset(self):
        self.similarities = [None] * self.detect_count


class DetectorBenchmark(Detector):

    def __init__(self):
        self.size = 16
        self.num_pixels = self.size * self.size

        self.capturer = xbmc.RenderCapture()
        self.capturer.capture(self.size, self.size)

        self.raw_data = [None, None]
        self.greyscale_data = [None, None]
        self.average_hashes = [None, None]
        self.median_hashes = [None, None]
        self.difference_hashes = [None, None]
        self.local_hashes = [None, None]

        self.show_output = False
        self.num_runs = 1

        self.detector = None
        self.running = False
        self.sigterm = False

    def test(self):
        if self.running:
            return
        self.running = True

        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.sigterm:
            raw = self.capturer.getImage()
            monitor.waitForAbort(1)
            if not raw:
                continue

            greyscale = convert_greyscale(raw)

            now = datetime.datetime.now()
            for i in range(self.num_runs):
                average_hash = calc_average_hash(greyscale)
            a_delta = (datetime.datetime.now() - now).total_seconds()

            now = datetime.datetime.now()
            for i in range(self.num_runs):
                median_hash = calc_median_hash(greyscale)
            m_delta = (datetime.datetime.now() - now).total_seconds()

            now = datetime.datetime.now()
            for i in range(self.num_runs):
                difference_hash = calc_xy_diff_hash(greyscale)
            d_delta = (datetime.datetime.now() - now).total_seconds()

            now = datetime.datetime.now()
            for i in range(self.num_runs):
                local_hash = calc_local_hash(greyscale)
            l_delta = (datetime.datetime.now() - now).total_seconds()

            del self.raw_data[0]
            self.raw_data.append(raw)

            del self.greyscale_data[0]
            self.greyscale_data.append(greyscale)

            del self.average_hashes[0]
            self.average_hashes.append(average_hash)

            del self.median_hashes[0]
            self.median_hashes.append(median_hash)

            del self.difference_hashes[0]
            self.difference_hashes.append(difference_hash)

            del self.local_hashes[0]
            self.local_hashes.append(local_hash)

            similarity = calc_similarity(
                self.greyscale_data[0],
                self.greyscale_data[1],
                equal_margin
            )
            if similarity is not None:
                similarity = calc_similarity(
                    self.average_hashes[0],
                    self.average_hashes[1]
                )
                if self.show_output:
                    print_hash(
                        self.average_hashes[0],
                        self.average_hashes[1],
                        self.size,
                        self.num_pixels
                    )
                log('AHash compare: {0:1.2f} in {1:1.4f}s'.format(
                    similarity,
                    a_delta
                ), 2)

                similarity = calc_similarity(
                    self.median_hashes[0],
                    self.median_hashes[1]
                )
                if self.show_output:
                    print_hash(
                        self.median_hashes[0],
                        self.median_hashes[1],
                        self.size,
                        self.num_pixels
                    )
                log('MHash compare: {0:1.2f} in {1:1.4f}s'.format(
                    similarity,
                    m_delta
                ), 2)

                similarity = calc_similarity(
                    self.difference_hashes[0],
                    self.difference_hashes[1]
                )
                if self.show_output:
                    print_hash(
                        self.difference_hashes[0],
                        self.difference_hashes[1],
                        self.size
                    )
                log('DHash compare: {0:1.2f} in {1:1.4f}s'.format(
                    similarity,
                    d_delta
                ), 2)

                similarity = calc_similarity(
                    self.local_hashes[0],
                    self.local_hashes[1]
                )
                if self.show_output:
                    print_hash(
                        self.local_hashes[0],
                        self.local_hashes[1],
                        self.size,
                        self.num_pixels
                    )
                log('LHash compare: {0:1.2f} in {1:1.4f}s'.format(
                    similarity,
                    l_delta
                ), 2)
                log('=======================', 2)

        self.running = False
        self.sigterm = False
