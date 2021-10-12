# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from __future__ import absolute_import, division, unicode_literals
from PIL import Image, ImageChops, ImageFilter
from settings import SETTINGS


_RADIAL_MASK = [None]
DETAIL_FILTER = ImageFilter.ModeFilter(3)
FIND_EDGES = ImageFilter.FIND_EDGES()
UNSHARP_MASK = ImageFilter.UnsharpMask(radius=2, percent=150, threshold=16)


def _min_max(value, min_value, max_value):
    return (min_value if value <= min_value
            else max_value if value >= max_value
            else value)


def image_bit_depth(image, bit_depth):
    num_levels = 2 ** bit_depth
    bit_mask = ~((2 ** (8 - bit_depth)) - 1)
    scale = num_levels / (num_levels - 1)

    return image.point([scale * (i & bit_mask) for i in range(256)])


def image_auto_level(image, cutoff_lo=0, cutoff_hi=100,
                     cutoff_method='count', clip=False):
    if cutoff_hi - cutoff_lo == 100:
        min_value, max_value = image.getextrema()

    elif cutoff_method == 'level':
        levels = [value for value, num in enumerate(image.histogram()) if num]
        percentage = len(levels) / 100
        cutoff_hi = max(cutoff_hi, cutoff_lo + (1 / percentage))
        cutoff_lo = int(cutoff_lo * percentage)
        cutoff_hi = int(cutoff_hi * percentage) - 1

        min_value = levels[cutoff_lo]
        max_value = levels[cutoff_hi]

    elif cutoff_method == 'count':
        levels = image.histogram()
        percentage = sum(levels) / 100
        if not percentage:
            return image
        cutoff_lo = int(cutoff_lo * percentage)
        cutoff_hi = int(cutoff_hi * percentage)

        running_total = 0
        min_value = 0
        max_value = 255
        for value, num in enumerate(levels):
            if not num:
                continue

            running_total += num
            if running_total <= cutoff_lo:
                min_value = value
            elif running_total > cutoff_hi:
                max_value = value
                break

    scale = 1
    offset = 0
    if not clip:
        scale = 255 / ((max_value - min_value) or 1)
        offset = scale * min_value
        min_value = 0
        max_value = 255

    return image.point([
        _min_max(int(scale * i - offset), min_value, max_value)
        for i in range(256)
    ])


def image_filter(image, filter_method, mask=False):
    filtered_image = image.filter(filter_method)

    if not mask:
        return filtered_image

    if not _RADIAL_MASK[0] or image.size != _RADIAL_MASK[0].size:
        radial_mask = Image.radial_gradient('L')
        radial_mask = radial_mask.resize(image.size, resample=Image.HAMMING)
        radial_mask = image_bit_depth(radial_mask, 3)
        radial_mask = image_auto_level(radial_mask, 25, 87.5,
                                       cutoff_method='level', clip=True)
        if SETTINGS.detector_debug_save:
            radial_mask.save(SETTINGS.detector_save_path + '0_mask.bmp')
        _RADIAL_MASK[0] = radial_mask

    return image.paste(filtered_image, mask=_RADIAL_MASK[0])


def image_format(image, buffer_size):
    # Convert captured image data from BGRA to RGBA
    image[0::4], image[2::4] = image[2::4], image[0::4]

    # Convert to greyscale to reduce size of data by a factor of 4
    image = Image.frombuffer(
        'RGBA', buffer_size, image, 'raw', 'RGBA', 0, 1
    ).convert('L')

    return image


def image_multiply_mask(mask, original):
    image = ImageChops.multiply(mask, original)
    histogram = original.histogram()
    target = 0.05 * max(histogram[0], sum(histogram[1:]))

    for _ in range(10):
        image = ImageChops.multiply(image, original)
        significant_pixels = sum(image.histogram()[1:])
        if significant_pixels <= target:
            break

    return image


def image_resize(image, size, method=None):
    if size and size != image.size:
        image = image.resize(
            size, resample=(method or SETTINGS.detector_resize_method)
        )

    return image
