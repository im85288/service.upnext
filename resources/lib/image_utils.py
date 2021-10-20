# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from __future__ import absolute_import, division, unicode_literals
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from settings import SETTINGS


_PRECOMPUTED = {}


def _min_max(value, min_value=0, max_value=255):
    if value <= min_value:
        return min_value
    if value >= max_value:
        return max_value
    return value


def _box_fade_mask(size, level_start, level_stop, border_size, steps, power):
    steps_scale = steps ** power
    padding_scale = border_size / steps_scale
    level_scale = (level_stop - level_start) / steps_scale

    element = Image.new('L', size, level_start)
    for step in range(steps + 1):
        step_scale = step ** power
        padding = max(step, int(step_scale * padding_scale))
        level = level_start + int(step_scale * level_scale)

        border = _precompute('BORDER_BOX,1,1,{0}'.format(padding), size)
        element.paste(level, box=border['box'])

    return element


def _border_box(size, horizontal_segments, vertical_segments, border_size):
    width, height = size

    border_left_right = width % horizontal_segments
    border_left = border_left_right // 2
    border_right = width - border_left_right + border_left

    border_top_bottom = height % vertical_segments
    border_top = border_top_bottom // 2
    border_bottom = height - border_top_bottom + border_top

    element = {
        'box': [
            border_left + border_size,
            border_top + border_size,
            border_right - border_size,
            border_bottom - border_size,
        ],
        'size': size,
    }
    return element


def _border_mask(size, border_size, border_colour, fill_colour):
    element = Image.new('L', size, border_colour)

    if border_size < 0:
        size = (size[0] + 2 * border_size, size[1] + 2 * border_size)
        border_size = -border_size
    border = _precompute('BORDER_BOX,1,1,{0}'.format(border_size), size)

    element.paste(fill_colour, box=border['box'])
    return element


def _precompute(method, size=None):
    element = _PRECOMPUTED.get(method)
    if element:
        image_size = getattr(element, 'size', None)
        if size == image_size:
            return element
        if not image_size and size == element['size']:
            return element

    element, _, args = method.partition(',')
    args = [int(arg) for arg in args.split(',') if arg]

    if element == 'BOX_FADE_MASK':
        element = _box_fade_mask(size, *args)

    elif element == 'BORDER_BOX':
        element = _border_box(size, *args)

    elif element == 'BORDER_MASK':
        element = _border_mask(size, *args)

    elif element == 'RankFilter':
        filter_size = args[0]
        rank = int(filter_size * filter_size * args[1] / 100)
        element = ImageFilter.RankFilter(filter_size, rank)

    else:
        element = getattr(ImageFilter, element)
        if callable(element):
            element = element(*args)

    _PRECOMPUTED[method] = element
    return element


def image_auto_contrast(image, cutoff=(0, 100, 0.33)):  # pylint: disable=too-many-locals
    segments = 8

    image = image_auto_level(image, *cutoff)
    crop_box = _precompute(
        'BORDER_BOX,{0},{0},0'.format(segments),
        image.size
    )['box']
    cropped_image = image.crop(crop_box)
    output = cropped_image.copy()

    segment_width = output.size[0] // segments
    segment_height = output.size[1] // segments
    segment_size = (segment_width, segment_height)

    border_size = max(5, int(0.25 * min(segment_size)))
    segment_border_box = _precompute(
        'BORDER_BOX,1,1,-{0}'.format(border_size),
        segment_size
    )['box']
    segment_mask = _precompute(
        'BOX_FADE_MASK,0,255,{0},{0},1'.format(border_size * 2),
        (segment_width + 2 * border_size, segment_height + 2 * border_size)
    )

    for vertical_idx in range(segments):
        for horizontal_idx in range(segments):
            horizontal_position = horizontal_idx * segment_width
            vertical_position = vertical_idx * segment_height
            new_segment_location = [
                segment_border_box[0] + horizontal_position,
                segment_border_box[1] + vertical_position,
                segment_border_box[2] + horizontal_position,
                segment_border_box[3] + vertical_position,
            ]
            new_segment = cropped_image.crop(new_segment_location)
            new_segment = image_auto_level(new_segment, *cutoff)

            output.paste(new_segment, box=new_segment_location,
                         mask=segment_mask)

    image.paste(output, box=crop_box)
    return image


def image_auto_level(image, min_value=0, max_value=100, clip=0):
    if max_value - min_value == 100:
        min_value, max_value = image.getextrema()

    else:
        levels = [value for value, num in enumerate(image.histogram()) if num]
        percentage = len(levels) / 100

        max_value = max(max_value, min_value + (1 / percentage))
        max_value = int(max_value * percentage) - 1
        max_value = levels[max_value]

        min_value = int(min_value * percentage)
        min_value = levels[min_value]

    scale = 1
    offset = 0
    if 1 > clip >= 0:
        clip = 255 * _min_max((max_value - min_value) / 255, clip, 1)
        scale = 255 / _min_max(clip, 1, 255)
        offset = scale * min_value
        min_value = 0
        max_value = 255

    return image.point([
        _min_max(int(scale * i - offset), min_value, max_value)
        for i in range(256)
    ])


def image_bit_depth(image, bit_depth):
    num_levels = 2 ** bit_depth
    bit_mask = ~((2 ** (8 - bit_depth)) - 1)
    scale = num_levels / (num_levels - 1)

    return image.point([scale * (i & bit_mask) for i in range(256)])


def image_conditional_filter(image, rules=((), ()), output=None,  # pylint: disable=too-many-locals
                             filter_args=(None, )):
    aggregate_image = image_filter(image, *filter_args)
    data = enumerate(zip(image.getdata(), aggregate_image.getdata()))
    inclusions = enumerate(rules[0])
    exclusions = enumerate(rules[1])
    width = image.size[0]

    if SETTINGS.detector_debug_save:
        data = tuple(data)
        inclusions = tuple(inclusions)
        exclusions = tuple(exclusions)
        rules = inclusions + exclusions

        aggregate_image.save('{0}conditional_{1}.bmp'.format(
            SETTINGS.detector_save_path, filter_args[0]))

        for idx, (local_min, local_max, percent_lo, percent_hi) in rules:
            debug_output = Image.new('L', image.size, 0)
            draw_canvas = ImageDraw.Draw(debug_output)
            draw_canvas.point([
                (idx % width, idx // width)
                for idx, (pixel, aggregate) in data
                if (local_max >= aggregate > local_min)
                and (
                    not aggregate
                    or percent_hi >= pixel / aggregate > percent_lo
                )
            ], fill=255)
            debug_output.save('{0}conditional_{1}_{2}.bmp'.format(
                SETTINGS.detector_save_path, filter_args[0], rules[idx]))

    if output != 'FILTER':
        image = Image.new('L', image.size, 0)

    if output == 'THRESHOLD':
        draw_canvas = ImageDraw.Draw(image)
        _ = [[
            draw_canvas.point((idx % width, idx // width), fill=pixel)
            for idx, (pixel, aggregate) in data
            if (local_max >= aggregate > local_min)
            and (
                not aggregate
                or percent_hi >= pixel / aggregate > percent_lo
            )
            and not [
                1 for _, (local_min, local_max, percent_lo, percent_hi)
                in exclusions
                if (local_max >= aggregate > local_min)
                and (
                    not aggregate
                    or percent_hi >= pixel / aggregate > percent_lo
                )
            ]
        ] for _, (local_min, local_max, percent_lo, percent_hi) in inclusions]

    elif output[:6] == 'FILTER':
        draw_canvas = ImageDraw.Draw(image)
        _ = [[
            draw_canvas.point((idx % width, idx // width), fill=aggregate)
            for idx, (pixel, aggregate) in data
            if (local_max >= aggregate > local_min)
            and (
                not aggregate
                or percent_hi >= pixel / aggregate > percent_lo
            )
            and not [
                1 for _, (local_min, local_max, percent_lo, percent_hi)
                in exclusions
                if (local_max >= aggregate > local_min)
                and (
                    not aggregate
                    or percent_hi >= pixel / aggregate > percent_lo
                )
            ]
        ] for _, (local_min, local_max, percent_lo, percent_hi) in inclusions]

    else:  # if output == 'MASK':
        draw_canvas = ImageDraw.Draw(image)
        _ = [
            draw_canvas.point([
                (idx % width, idx // width)
                for idx, (pixel, aggregate) in data
                if (local_max >= aggregate > local_min)
                and (
                    not aggregate
                    or percent_hi >= pixel / aggregate > percent_lo
                )
                and not [
                    1 for _, (local_min, local_max, percent_lo, percent_hi)
                    in exclusions
                    if (local_max >= aggregate > local_min)
                    and (
                        not aggregate
                        or percent_hi >= pixel / aggregate > percent_lo
                    )
                ]
            ], fill=255)
            for _, (local_min, local_max, percent_lo, percent_hi) in inclusions
        ]

    return image


def image_filter(image, method, extent=None, original=None, difference=False):
    if difference:
        difference = original.copy() if original else image

    if original:
        original = original.copy()
        filtered_image = original.filter(_precompute(method))
    else:
        filtered_image = image.filter(_precompute(method))

    if not extent or extent == 'ALL':
        mask = None

    elif extent == 'TRIM':
        border_size = max(1, int(0.005 * max(image.size)))
        mask = _precompute(
            'BORDER_MASK,{0},0,255'.format(border_size),
            image.size
        )
        image = mask

    else:
        background, _, direction = extent.partition('_')

        if background == 'BLACK':
            image = Image.new('L', image.size, 0)

        border_size = max(10, int(0.25 * min(image.size)))
        mask = (255, 0) if direction == 'IN' else (0, 255)
        mask = _precompute(
            'BOX_FADE_MASK,{1},{2},{0},{0},1'.format(border_size, *mask),
            image.size
        )

    image = image.copy()
    image.paste(filtered_image, mask=mask)

    if difference:
        return ImageChops.difference(difference, image)
    return image


def image_format(image, buffer_size):
    if isinstance(image, Image.Image):
        return image.convert('L')

    # Convert captured image data from BGRA to RGBA
    image[0::4], image[2::4] = image[2::4], image[0::4]

    # Convert to greyscale to reduce size of data by a factor of 4
    image = Image.frombuffer(
        'RGBA', buffer_size, image, 'raw', 'RGBA', 0, 1
    ).convert('L')

    return image


def image_invert(image):
    return ImageChops.invert(image)


def image_multiply_mask(image, base_image, reduction=25):
    image = ImageChops.multiply(image, base_image)
    total_pixels = image.size[0] * image.size[1]
    histogram = base_image.histogram()
    significant_pixels = max(histogram[0], total_pixels - histogram[0])
    target = (100 - reduction) * significant_pixels / 100

    for _ in range(10):
        image = ImageChops.multiply(image, base_image)
        significant_pixels = total_pixels - image.histogram()[0]
        if significant_pixels <= target:
            break

    return image


def image_replace(image, replacement_image=None):
    return replacement_image.copy() if replacement_image else image.copy()


def image_resize(image, size, method=None):
    if size != image.size:
        image = image.resize(
            size, resample=(method or SETTINGS.detector_resize_method)
        )

    return image
