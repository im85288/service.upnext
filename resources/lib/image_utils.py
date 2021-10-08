# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from __future__ import absolute_import, division, unicode_literals
from PIL import Image, ImageChops, ImageFilter, ImageMorph
from settings import SETTINGS


UNSHARP_MASK = ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
if SETTINGS.detector_filter:
    FIND_EDGES = ImageFilter.FIND_EDGES()
    DETAIL_FILTER = ImageFilter.ModeFilter(3)
    DENOISE_LUT = ImageMorph.LutBuilder(patterns=[
        '4:(.0. 01. ...)->0', '4:(.1. 10. ...)->1'
    ]).build_lut()
    DILATE_LUT = ImageMorph.LutBuilder(patterns=[
        '4:(.1. .0. ...)->1', '4:(1.. .0. ...)->1'
    ]).build_lut()


def _radial_mask(size, _cache=[None]):  # pylint: disable=dangerous-default-value
    if not _cache[0] or size != _cache[0].size:
        mask = Image.radial_gradient('L')
        mask = mask.resize(size, resample=Image.HAMMING)
        mask = image_bit_depth(mask, 3)
        mask = image_auto_level(mask, 12.5, 87.5, True)
        _cache[0] = mask

    return _cache[0]


def image_bit_depth(image, bit_depth):
    output_values = 2 ** bit_depth
    band = 256 / output_values
    scale = 256 / (output_values - 1)

    return image.point([
        min(255, max(0, int(scale * (i // band))))
        for i in range(256)
    ])


def image_auto_level(image, cutoff_lo=0, cutoff_hi=100, clip=False):
    if cutoff_hi - cutoff_lo == 100:
        min_value, max_value = image.getextrema()
    else:
        histogram = image.histogram()
        percent_total = sum(histogram) // 100
        if not percent_total:
            return image
        cutoff_lo = cutoff_lo * percent_total
        cutoff_hi = cutoff_hi * percent_total

        running_total = 0
        min_value = 0
        max_value = 255
        for value, num in enumerate(histogram):
            if not num:
                continue

            running_total += num
            if running_total <= cutoff_lo:
                min_value = value
            elif running_total > cutoff_hi:
                max_value = value
                break

    scale = 255 / ((max_value - min_value) or 1)
    offset = 0
    if not clip:
        offset = min_value
        min_value = 0
        max_value = 255

    return image.point([
        min(max_value, max(min_value, int(scale * (i - offset))))
        for i in range(256)
    ])


def image_filter(image, filter_method, mask=False):
    filtered_image = image.filter(filter_method)

    if mask:
        return image.paste(filtered_image, mask=_radial_mask(image.size))
    return filtered_image


def image_format(image, buffer_size):
    # Convert captured image data from BGRA to RGBA
    image[0::4], image[2::4] = image[2::4], image[0::4]

    # Convert to greyscale to reduce size of data by a factor of 4
    image = Image.frombuffer(
        'RGBA', buffer_size, image, 'raw', 'RGBA', 0, 1
    ).convert('L')

    return image


def image_morph(image, precompiled, *morph_list):
    for morph in morph_list:
        if not precompiled:
            morph = ImageMorph.LutBuilder(patterns=morph).build_lut()
        _, image = ImageMorph.MorphOp(lut=morph).apply(image)

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
