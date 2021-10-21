# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from __future__ import absolute_import, division, unicode_literals
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from settings import SETTINGS


_PRECOMPUTED = {}


def _border_box(size, horizontal_segments, vertical_segments,  # pylint: disable=too-many-locals
                left_size, top_size=None, right_size=None, bottom_size=None):
    width, height = size

    border_left_right = width % horizontal_segments
    border_left = border_left_right // 2
    border_right = width - border_left_right + border_left

    border_top_bottom = height % vertical_segments
    border_top = border_top_bottom // 2
    border_bottom = height - border_top_bottom + border_top

    if top_size is None:
        top_size = right_size = bottom_size = left_size
    if right_size is None:
        right_size = left_size
        bottom_size = top_size
    if bottom_size is None:
        bottom_size = top_size

    element = {
        'box': [
            border_left + left_size,
            border_top + top_size,
            border_right - right_size,
            border_bottom - bottom_size,
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


def _calc_median(vals):
    """Method to calculate median value of a list of values by sorting and
        indexing the list"""

    num_vals = len(vals)
    pivot = num_vals // 2
    vals = sorted(vals)
    if num_vals % 2:
        return vals[pivot]
    return (vals[pivot] + vals[pivot - 1]) / 2


def _fade_mask(size, level_start, level_stop, steps, power,  # pylint: disable=too-many-locals
               left_size, top_size=None, right_size=None, bottom_size=None,
               _int=int, _max=max):
    if top_size is None:
        top_size = right_size = bottom_size = left_size
    if right_size is None:
        right_size = left_size
        bottom_size = top_size
    if bottom_size is None:
        bottom_size = top_size

    steps_scale = steps ** power
    padding_left_scale = left_size / steps_scale
    padding_top_scale = top_size / steps_scale
    padding_right_scale = right_size / steps_scale
    padding_bottom_scale = bottom_size / steps_scale
    level_scale = (level_stop - level_start) / steps_scale

    element = Image.new('L', size, level_start)
    for step in range(steps + 1):
        step_scale = step ** power
        padding_left = _max(left_size and 1,
                            _int(step_scale * padding_left_scale))
        padding_top = _max(top_size and 1,
                           _int(step_scale * padding_top_scale))
        padding_right = _max(right_size and 1,
                             _int(step_scale * padding_right_scale))
        padding_bottom = _max(bottom_size and 1,
                              _int(step_scale * padding_bottom_scale))
        level = level_start + _int(step_scale * level_scale)

        border = _precompute('BORDER_BOX,1,1,{0},{1},{2},{3}'.format(
            padding_left, padding_top, padding_right, padding_bottom), size)
        element.paste(level, box=border['box'])

    element = apply_filter(element, 'BoxBlur,{0}'.format(min(size) // 8))
    return element


def _precompute(method, size=None, _int=int, _float=float):
    element = _PRECOMPUTED.get(method)
    if element:
        image_size = getattr(element, 'size', None)
        if size == image_size:
            return element
        if not image_size and size == element['size']:
            return element

    element, _, args = method.partition(',')
    args = [_float(arg) if '.' in arg else _int(arg)
            for arg in args.split(',') if arg]

    if element == 'BINARY_LUT':
        element = (0, ) * 128 + (1, ) * 128

    elif element == 'BORDER_BOX':
        element = _border_box(size, *args)

    elif element == 'BORDER_MASK':
        element = _border_mask(size, *args)
        if SETTINGS.detector_debug_save:
            element.save('{0}_{1}.bmp'.format(
                SETTINGS.detector_save_path, method))

    elif element == 'FADE_MASK':
        element = _fade_mask(size, *args)
        if SETTINGS.detector_debug_save:
            element.save('{0}_{1}.bmp'.format(
                SETTINGS.detector_save_path, method))

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


def adaptive_contrast(image, segments=8, cutoff=(5, 95, (0.25, None)), debug=False):  # pylint: disable=too-many-locals
    crop_box = _precompute(
        'BORDER_BOX,{0},{0},0'.format(segments),
        image.size
    )['box']
    cropped_image = image.crop(crop_box)
    output = cropped_image.copy()

    segment_width = output.size[0] // segments
    segment_height = output.size[1] // segments

    left_border = max(5, int(1 * segment_width))
    top_border = max(5, int(1 * segment_height))
    segment_border_box = _precompute(
        'BORDER_BOX,1,1,{0},{1}'.format(-left_border, -top_border),
        (segment_width, segment_height)
    )['box']
    segment_mask = _precompute(
        'FADE_MASK,0,255,10,0.33,{0},{1}'.format(left_border, top_border),
        (segment_width + 2 * left_border, segment_height + 2 * top_border)
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
            new_segment = auto_level(new_segment, *cutoff)

            output.paste(new_segment, box=new_segment_location,
                         mask=segment_mask)
            if debug and SETTINGS.detector_debug_save:
                output.save('{0}{1}[{2}.{3}].bmp'.format(
                    SETTINGS.detector_save_path, debug,
                    vertical_idx, horizontal_idx
                ))

    image.paste(output, box=crop_box)
    return image


def auto_level(image, min_value=0, max_value=100, clip=(0, None), _int=int):
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

    if min_value >= max_value:
        return image

    if clip[0] < 1:
        offset = 0
        if clip[1] == 0:
            scale = max_value
        elif clip[1] == 1:
            scale = 255 - min_value
            offset = min_value
        else:
            scale = 255

        scale = 1 / max(clip[0], (max_value - min_value) / scale)
        offset = scale * (min_value - offset)

        return image.point([
            _int(scale * i - offset)
            for i in range(256)
        ])

    return image.point([
        min_value if i <= min_value else max_value if i >= max_value else i
        for i in range(256)
    ])


def apply_filter(image, method, extent=None, original=None, difference=False):
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
            'FADE_MASK,{1},{2},{0},1,{0}'.format(border_size, *mask),
            image.size
        )

    image = image.copy()
    image.paste(filtered_image, mask=mask)

    if difference:
        return ImageChops.difference(difference, image)
    return image


def conditional_filter(image, rules=((), ()), output=None,  # pylint: disable=too-many-locals
                       filter_args=(None, ), debug=False):
    aggregate_image = apply_filter(image, *filter_args)
    data = enumerate(zip(image.getdata(), aggregate_image.getdata()))
    inclusions = enumerate(rules[0])
    exclusions = enumerate(rules[1])
    width = image.size[0]

    if debug and SETTINGS.detector_debug_save:
        data = tuple(data)
        inclusions = tuple(inclusions)
        exclusions = tuple(exclusions)
        rules = inclusions + exclusions

        aggregate_image.save('{0}{1}[{2}].bmp'.format(
            SETTINGS.detector_save_path, debug, filter_args[0]
        ))

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
            debug_output.save('{0}{1}[{2}][{3}].bmp'.format(
                SETTINGS.detector_save_path, debug,
                filter_args[0], rules[idx]
            ))

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


def create_hash(image, _abs=abs):
    # Transform image to show absolute deviation from median pixel luma
    median_pixel = _calc_median(image.getdata())
    image = image.point([_abs(i - median_pixel) for i in range(256)])

    # Calculate median absolute deviation from the median to represent
    # significant pixels and use transformed image as the hash of the
    # current video frame
    median_pixel = _calc_median(image.getdata())
    image = image.point([255 if (i > median_pixel) else 0 for i in range(256)])

    return image


def detail_reduce(image, base_image, reduction=25,
                  _multiply=ImageChops.multiply):
    image = _multiply(image, base_image)
    total_pixels = image.size[0] * image.size[1]
    histogram = base_image.histogram()
    significant_pixels = max(histogram[0], total_pixels - histogram[0])
    target = (100 - reduction) * significant_pixels / 100

    for _ in range(10):
        image = _multiply(image, base_image)
        significant_pixels = total_pixels - image.histogram()[0]
        if significant_pixels <= target:
            break

    return image


def deviation(image, percentile, skip_levels, filter_size=3, rank=50):
    aggregate_image = apply_filter(
        image,
        'RankFilter,{0},{1}'.format(filter_size, rank),
        'ALL', None, True
    )
    histogram = aggregate_image.histogram()

    percentile = percentile / 100
    target = int(
        ((image.size[0] * image.size[1]) - sum(histogram[:skip_levels]))
        * percentile
    )
    running_total = 0

    for val, num in enumerate(histogram[skip_levels:]):
        if not num:
            continue

        running_total += num
        if running_total > target:
            target = val + skip_levels
            break
    else:
        target = 255

    mask = aggregate_image.point(
        [255 if (i < target) else 0 for i in range(256)]
    )
    image.paste(0, mask=mask)

    return image


def export_data(image):
    return tuple(image.point(_precompute('BINARY_LUT')).getdata())


def import_data(image=None, data=None, buffer_size=None):
    if isinstance(data, Image.Image):
        image = data

    elif isinstance(data, bytearray):
        # Convert captured image data from BGRA to RGBA
        data[0::4], data[2::4] = data[2::4], data[0::4]

        # Convert to greyscale to reduce size of data by a factor of 4
        image = Image.frombuffer(
            'RGBA', buffer_size, data, 'raw', 'RGBA', 0, 1
        )

    if isinstance(image, Image.Image):
        image = image.convert('L')

    return image


def posterise(image, bit_depth):
    num_levels = 2 ** bit_depth
    bit_mask = ~((2 ** (8 - bit_depth)) - 1)
    scale = num_levels / (num_levels - 1)

    return image.point([scale * (i & bit_mask) for i in range(256)])


def process(image, pipeline, save_file=None):
    if isinstance(image, Image.Image):
        image = image.copy()

    for step, args in enumerate(pipeline):
        method = args.pop(0)

        target = save_file and SETTINGS.detector_debug_save
        if target:
            target = '{0}_{1}_{2}'.format(save_file, step, method.__name__)
            if args:
                target += '({0})'.format([
                    arg for arg in args
                    if isinstance(arg, (str, int, tuple, list))
                    and arg != 'DEBUG'
                ])
                if args[-1] == 'DEBUG':
                    args[-1] = target

        image = method(image, *args) or image

        if not isinstance(image, Image.Image):
            break

        if not target:
            continue

        try:
            image.save('{0}{1}.bmp'.format(
                SETTINGS.detector_save_path, target
            ))
        except (IOError, OSError):
            pass

    return image


def replace_with_copy(image, replacement_image=None):
    return replacement_image.copy() if replacement_image else image.copy()


def resize(image, size, method=None):
    if size != image.size:
        image = image.resize(
            size, resample=(method or SETTINGS.detector_resize_method)
        )

    return image
