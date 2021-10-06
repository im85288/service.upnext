# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from PIL import Image, ImageChops, ImageFilter, ImageMorph
from settings import SETTINGS


UNSHARP_MASK = ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
if SETTINGS.detector_filter:
    FIND_EDGES = ImageFilter.FIND_EDGES()
    DETAIL_REDUCE_FILTER = ImageFilter.ModeFilter(3)
    DENOISE_LUT = ImageMorph.LutBuilder(patterns=[
        '4:(.0. 01. ...)->0'
    ]).build_lut()
    DILATE_LUT = ImageMorph.LutBuilder(patterns=[
        '4:(.1. .0. ...)->1', '4:(1.. .0. ...)->1'
    ]).build_lut()


def _radial_mask(size, output_cache=[None]):  # pylint: disable=dangerous-default-value
    if not output_cache[0] or size != output_cache[0].size:
        output_cache[0] = image_auto_level(
            Image.radial_gradient('L').resize(size, resample=Image.HAMMING),
            50, 100, True
        )

    return output_cache[0]


def image_auto_level(image, cutoff_lo=0, cutoff_hi=100, saturate=False):
    if cutoff_hi <= cutoff_lo:
        return image
    if cutoff_hi - cutoff_lo == 100:
        min_value, max_value = image.getextrema()
    else:
        histogram = image.histogram()[1:]
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
            elif running_total >= cutoff_hi:
                max_value = value
                break

    if max_value <= min_value:
        return image

    scale = 255 / (max_value - min_value)
    if saturate:
        min_value = 0

    return image.point([
        min(255, max(0,
            int((17 * (i // 16) - min_value) * scale)
        ))
        for i in range(256)
    ])


def image_filter(image, filter_method, mask=False):
    filtered_image = image.filter(filter_method)

    if mask:
        return image.paste(filtered_image, mask=_radial_mask(image.size))
    return filtered_image


def image_contrast(image, factor):
    data = image.getdata()
    mean = int((sum(data) / len(data)) + 0.5)
    image2 = Image.new('L', image.size, mean)

    return Image.blend(image2, image, factor)


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
