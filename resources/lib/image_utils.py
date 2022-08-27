# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements image manipulation and filtering helper functions"""

from __future__ import absolute_import, division, unicode_literals
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from settings import SETTINGS


_PRECOMPUTED = {
    '_STACK': [],
}


try:
    _FORMAT = unicode.format
    _SPLIT = unicode.split
except NameError:
    _FORMAT = str.format
    _SPLIT = str.split


def _bit_depth_lut(bit_depth, scale=None, _int=int):
    num_levels = 2 ** bit_depth
    bit_mask = ~((2 ** (8 - bit_depth)) - 1)
    scale = scale or num_levels / (num_levels - 1)

    element = [_int(scale * (i & bit_mask)) for i in range(256)]
    return element


def _border_box(size, horizontal_segments, vertical_segments, *box):  # pylint: disable=too-many-locals
    width, height = size

    border_left_right = width % horizontal_segments
    border_left = border_left_right // 2
    border_right = width - border_left_right + border_left

    border_top_bottom = height % vertical_segments
    border_top = border_top_bottom // 2
    border_bottom = height - border_top_bottom + border_top

    dimensions = len(box)
    if not dimensions:
        left = top = right = bottom = 0
    elif dimensions == 1:
        left = top = right = bottom = box[0]
    elif dimensions == 2:
        left = right = box[0]
        top = bottom = box[1]
    elif dimensions == 3:
        left, top, right = box
        bottom = top
    else:
        left, top, right, bottom = box

    element = {
        'box': [
            border_left + left,
            border_top + top,
            border_right - right,
            border_bottom - bottom,
        ],
        'size': size,
    }
    return element


def _border_mask(size, border_colour, fill_colour, *box):
    element = Image.new('L', size, border_colour)

    if len(box) == 1:
        border = box[0]
        if border < 0:
            size = (size[0] + 2 * border, size[1] + 2 * border)
            border = -border
        box = _precompute('BORDER_BOX,1,1,{0}'.format(border), size)['box']

    element.paste(fill_colour, box=box)
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


def _fade_mask(size, level_start, level_stop, steps, power, box,  # pylint: disable=too-many-arguments, too-many-locals
               _format=_FORMAT, _int=int, _max=max,
               _paste=Image.Image.paste):
    dimensions = len(box)
    if not dimensions:
        left = top = right = bottom = 0
    elif dimensions == 1:
        left = top = right = bottom = box[0]
    elif dimensions == 2:
        left = right = box[0]
        top = bottom = box[1]
    elif dimensions == 3:
        left, top, right = box
        bottom = top
    else:
        left, top, right, bottom = box[:4]

    steps_scale = steps ** power
    padding_left_scale = left / steps_scale
    padding_top_scale = top / steps_scale
    padding_right_scale = right / steps_scale
    padding_bottom_scale = bottom / steps_scale
    level_scale = (level_stop - level_start) / steps_scale

    element = Image.new('L', size, level_start)
    for step in range(steps + 1):
        step_scale = step ** power

        padding_left = _max(left and 1,
                            _int(step_scale * padding_left_scale))
        padding_top = _max(top and 1,
                           _int(step_scale * padding_top_scale))
        padding_right = _max(right and 1,
                             _int(step_scale * padding_right_scale))
        padding_bottom = _max(bottom and 1,
                              _int(step_scale * padding_bottom_scale))
        level = level_start + _int(step_scale * level_scale)

        border = _precompute(
            _format(
                'BORDER_BOX,1,1,{0},{1},{2},{3}',
                padding_left, padding_top, padding_right, padding_bottom
            ), size
        )

        _paste(element, level, box=border['box'])

    element = apply_filter(element, 'GaussianBlur,{0}'.format(min(size) // 8))
    return element


def _histogram_rank(input_data, percentile, skip_levels=0):
    if isinstance(input_data, Image.Image):
        total = input_data.size[0] * input_data.size[1]
        histogram = input_data.histogram()
    else:
        histogram = input_data
        total = sum(histogram)

    percentile = percentile / 100
    target = int((total - sum(histogram[:skip_levels])) * percentile)
    total = 0

    for val, num in enumerate(histogram[skip_levels:]):
        if not num:
            continue

        total += num
        if total > target:
            target = val + skip_levels
            break
    else:
        target = 255

    return target


def _precompute(method, size=None, debug=SETTINGS.detector_debug_save):
    element = _PRECOMPUTED.get(method)
    try:
        if element and size == getattr(element, 'size', element.get('size')):
            return element
    except AttributeError:
        pass

    element, _, args = method.partition(',')
    args = _to_numbers(args)

    if element == 'ALL_PASS_LUT':
        element = [255] * 256
        element[0] = 0
        debug = False

    elif element == 'BIT_DEPTH_LUT':
        element = _bit_depth_lut(*args)  # pylint: disable=no-value-for-parameter
        debug = False

    elif element == 'BORDER_BOX':
        element = _border_box(size, *args)  # pylint: disable=no-value-for-parameter
        debug = False

    elif element == 'BORDER_MASK':
        element = _border_mask(size, *args)  # pylint: disable=no-value-for-parameter

    elif element == 'FADE_MASK':
        # Split args to avoid Python2 syntax error in definition of _fade_mask
        args = args[:4] + [args[4:]]
        element = _fade_mask(size, *args)  # pylint: disable=no-value-for-parameter

    elif element == 'RankFilter':
        filter_size = args[0]
        max_size = filter_size * filter_size
        rank = min(max_size - 1, int(max_size * args[1] / 100))
        element = ImageFilter.RankFilter(filter_size, rank)
        debug = False

    else:
        element = getattr(ImageFilter, element)
        if callable(element):
            element = element(*args)
        debug = False

    if debug:
        element.save('{0}_{1}.bmp'.format(
            SETTINGS.detector_save_path, method
        ))

    _PRECOMPUTED[method] = element
    return element


def _process_args(args, image, sentinel='~',
                  _format=_FORMAT, _int=int, _split=_SPLIT):
    histogram = None

    for idx, arg in enumerate(args):
        try:
            if sentinel not in arg:
                continue
        except TypeError:
            continue

        prefix, placeholder, postfix = _split(arg, sentinel)
        placeholder = _int(placeholder)

        histogram = histogram if histogram else image.histogram()
        replacement = _histogram_rank(histogram, placeholder)

        if prefix or postfix:
            replacement = _format('{0}{1}{2}', prefix, placeholder, postfix)

        args[idx] = replacement

    return args


def _precision(number, decimal_places=3):
    factor = float(10 ** decimal_places)
    return int(number * factor) / factor


def _to_numbers(args, _int=int, _float=float, _split=_SPLIT):
    if not args:
        return []

    return [
        _float(arg) if '.' in arg else
        _int(arg) if arg else None
        for arg in _split(args, ',')
    ]


def adaptive_filter(image, sampling, method, args=(), save_file=None,  # pylint: disable=too-many-locals
                    _crop=Image.Image.crop, _copy=Image.Image.copy,
                    _format=_FORMAT, _int=int, _paste=Image.Image.paste,
                    _range=range, _save=Image.Image.save):
    segments, overlap, mask = sampling

    crop_box = _precompute(
        _format('BORDER_BOX,{0},{0},1', segments), image.size
    )
    crop_box = crop_box['box']
    cropped_image = _crop(image, crop_box)
    output = _copy(cropped_image)

    segment_width = output.size[0] // segments
    segment_height = output.size[1] // segments

    left_border = _int(overlap * segment_width)
    top_border = _int(overlap * segment_height)
    segment_border_box = _precompute(
        _format('BORDER_BOX,1,1,{0},{1}', -left_border, -top_border),
        (segment_width, segment_height)
    )
    segment_border_box = segment_border_box['box']

    mask = _precompute(
        _format('FADE_MASK,0,255,10,0.33,{0},{1}', left_border, top_border),
        (segment_width + 2 * left_border, segment_height + 2 * top_border)
    ) if mask else None

    for vertical_idx in _range(segments):
        for horizontal_idx in _range(segments):
            horizontal_position = horizontal_idx * segment_width
            vertical_position = vertical_idx * segment_height
            new_segment_location = [
                segment_border_box[0] + horizontal_position,
                segment_border_box[1] + vertical_position,
                segment_border_box[2] + horizontal_position,
                segment_border_box[3] + vertical_position,
            ]
            new_segment = _crop(cropped_image, new_segment_location)
            new_segment = method(new_segment, *args)

            _paste(output, new_segment, box=new_segment_location, mask=mask)
            if save_file and SETTINGS.detector_debug_save:
                _save(output, _format(
                    '{0}{1}[{2}.{3}].bmp',
                    SETTINGS.detector_save_path, save_file,
                    vertical_idx, horizontal_idx
                ))

    _paste(image, output, box=crop_box)
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


def apply_filter(image, method, extent=None, original=None, output_op=None):
    if output_op:
        original = original if original else image

    if original:
        original = original.copy()
        filtered_image = original.filter(_precompute(method))
    else:
        filtered_image = image.filter(_precompute(method))

    if not extent or extent == 'ALL':
        mask = None

    elif extent == 'TRIM':
        border = _precompute('BORDER_BOX,8,8,1', image.size)['box']
        mask = _precompute(
            'BORDER_MASK,0,255,{0},{1},{2},{3}'.format(*border), image.size
        )
        image = mask

    else:
        background, _, direction = extent.partition('_')

        if background == 'BLACK':
            image = Image.new('L', image.size, 0)

        border = max(10, int(0.25 * min(image.size)))
        mask = (255, 0) if direction == 'IN' else (0, 255)
        mask = _precompute(
            'FADE_MASK,{1},{2},{0},3,{0}'.format(border, *mask), image.size
        )

    image = image.copy()
    image.paste(filtered_image, mask=mask)

    if output_op:
        output_op = getattr(ImageChops, output_op)
        return output_op(original, image)
    return image


def conditional_filter(image, rules=((), ()), output=None,  # pylint: disable=too-many-locals
                       filter_args=(None, ), save_file=None,
                       _draw=ImageDraw.Draw, _format=_FORMAT,
                       _new=Image.new, _point=ImageDraw.ImageDraw.point,
                       _save=Image.Image.save, _tuple=tuple):
    aggregate_image = apply_filter(image, *filter_args)
    data = enumerate(zip(image.getdata(), aggregate_image.getdata()))
    inclusions = enumerate(rules[0])
    exclusions = enumerate(rules[1])
    width = image.size[0]

    if save_file and SETTINGS.detector_debug_save:
        data = _tuple(data)
        inclusions = _tuple(inclusions)
        exclusions = _tuple(exclusions)
        rules = inclusions + exclusions

        aggregate_image.save(_format(
            '{0}{1}[{2}].bmp',
            SETTINGS.detector_save_path, save_file,
            filter_args[0]
        ))

        for idx, (local_min, local_max, percent_lo, percent_hi) in rules:
            debug_output = _new('L', image.size, 0)
            draw_canvas = _draw(debug_output)
            _point(draw_canvas, [
                (idx % width, idx // width)
                for idx, (pixel, aggregate) in data
                if (local_max >= aggregate > local_min)
                and (
                    not aggregate
                    or percent_hi >= pixel / aggregate > percent_lo
                )
            ], fill=255)
            _save(debug_output, _format(
                '{0}{1}[{2}][{3}].bmp',
                SETTINGS.detector_save_path, save_file,
                filter_args[0],
                rules[idx]
            ))

    if output != 'FILTER':
        image = _new('L', image.size, 0)

    if output == 'THRESHOLD':
        draw_canvas = _draw(image)
        _ = [[
            _point(draw_canvas, (idx % width, idx // width), fill=pixel)
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
        draw_canvas = _draw(image)
        _ = [[
            _point(draw_canvas, (idx % width, idx // width), fill=aggregate)
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
        draw_canvas = _draw(image)
        _ = [
            _point(draw_canvas, [
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


def detail_reduce(image, base_image, reduction=25,
                  _histogram=Image.Image.histogram, _mul=ImageChops.multiply):
    total_pixels = image.size[0] * image.size[1]
    histogram = _histogram(base_image)
    if _histogram_rank(histogram, reduction, 0) < 16:
        reduction = 0
    significant_pixels = total_pixels - histogram[0]
    target = (100 - reduction) * significant_pixels / 100

    for _ in range(10):
        image = _mul(image, base_image)
        new_significant_pixels = total_pixels - _histogram(image)[0]
        if (new_significant_pixels <= target or
                0.9 * significant_pixels < new_significant_pixels):
            break
        significant_pixels = new_significant_pixels

    return image


def export_data(image):
    lut = _precompute('BIT_DEPTH_LUT,1,0.0078125')

    return tuple(image.point(lut).getdata())


def has_credits(image, filtered_image, save_file=None):
    filtered_image = apply_filter(filtered_image, 'BoxBlur,1')
    filtered_entropy = image.entropy(mask=filtered_image)

    expanded_image = apply_filter(filtered_image, 'BoxBlur,20')
    expanded_entropy = image.entropy(mask=expanded_image)

    if filtered_entropy and expanded_entropy:
        filtered_image = filtered_image.point(
            _precompute('ALL_PASS_LUT')
        )
        expanded_image = expanded_image.point(
            _precompute('ALL_PASS_LUT')
        )

        output_image = Image.new('L', image.size, 0)
        output_image.paste(image, mask=expanded_image)

        if save_file and SETTINGS.detector_debug_save:
            output_image.save('{0}{1}_2.bmp'.format(
                SETTINGS.detector_save_path, save_file
            ))

        return (expanded_entropy / filtered_entropy) < 1.10, output_image

    return False, None


def image_stack(index):
    def _image_stack_fetch():
        return _PRECOMPUTED['_STACK'][index]
    return _image_stack_fetch


def import_data(input_data, buffer_size=None):
    if isinstance(input_data, Image.Image):
        image = input_data

    elif isinstance(input_data, bytearray):
        # Convert captured image data from BGRA to RGBA
        input_data[0::4], input_data[2::4] = input_data[2::4], input_data[0::4]

        image = Image.frombuffer(
            'RGBA', buffer_size, input_data, 'raw', 'RGBA', 0, 1
        )

    image = image.convert('HSV').getchannel(2)

    return image


def output_histogram(input_data, scale_to_max=False, save_file=None):
    if isinstance(input_data, Image.Image):
        histogram = input_data.histogram()
    else:
        histogram = input_data

    padding = 4
    size = (len(histogram) + padding) * 2
    image = Image.new('L', (size, size), 255)
    draw_canvas = ImageDraw.Draw(image)

    draw_canvas.rectangle(
        (padding - 2, padding - 2, size - padding + 1, size - padding + 2),
        fill=255, outline=0, width=1
    )

    x_axis = size - padding
    scale = max(histogram) if scale_to_max else sum(histogram)
    scale = 2 * len(histogram) / scale if scale else 0

    for idx, num in enumerate(histogram):
        line_colour = 0 if (idx + 2) % 8 == 1 else 191
        x_coord = padding + idx * 2
        y_coord = int(size - padding - num * scale)
        draw_canvas.line((x_coord, x_axis, x_coord, y_coord), line_colour, 1)

    if save_file:
        image.save('{0}{1}.bmp'.format(SETTINGS.detector_save_path, save_file))
        if isinstance(input_data, Image.Image):
            return None

    return image


def points_of_interest(image, percentile=50, skip_levels=0, _abs=abs):
    # Transform image to show absolute deviation from median pixel luma
    target = _histogram_rank(image, 50)
    image = image.point([_abs(i - target) for i in range(256)])

    # Calculate percentile of absolute deviation from the median to represent
    # significant pixels and use transformed image as the hash of the
    # current video frame
    target = _histogram_rank(image, percentile, skip_levels)
    image = image.point([255 if (i > target) else 0 for i in range(256)])

    return image


def posterise(image, bit_depth):
    lut = _precompute('BIT_DEPTH_LUT,{}'.format(bit_depth))

    return image.point(lut)


def process(data, queue, save_file=None, debug=SETTINGS.detector_debug_save,
            _append=list.append, _callable=callable, _copy=Image.Image.copy,
            _enumerate=enumerate, _float=float, _format=_FORMAT, _int=int,
            _isinstance=isinstance, _list=list, _pop=list.pop, _str=str,
            _save=Image.Image.save, _tuple=tuple):
    _PRECOMPUTED['_STACK'] = []
    if _isinstance(data, Image.Image):
        data = data.copy()
    debug = debug and save_file

    for step, args in enumerate(queue):
        method = _pop(args, 0)

        args_enum = _enumerate(args)
        if debug:
            args_enum = _tuple(args_enum)
            save_file = _format('{0}_{1}_{2}', debug, step, method.__name__)
            if args:
                save_file = _format('{1}{0}', [
                    arg if _isinstance(
                        arg, (_int, _float, _list, _str, _tuple)
                    )
                    else arg.__name__ if _callable(arg)
                    else type(arg).__name__
                    for _, arg in args_enum
                    if arg != 'DEBUG'
                ], save_file)

                for idx in [idx for idx, arg in args_enum if arg == 'DEBUG']:
                    args[idx] = save_file

        for idx in [idx for idx, arg in args_enum  # pylint: disable=undefined-loop-variable
                    if _callable(arg)
                    and arg.__name__ == '_image_stack_fetch']:
            args[idx] = args[idx]()

        output = method(data, *args)
        _append(_PRECOMPUTED['_STACK'], output)

        if _isinstance(output, Image.Image):
            data = _copy(output)
        elif output:
            data = output
            continue
        else:
            continue

        if not debug:
            continue

        try:
            _save(data, _format(
                '{0}{1}.bmp', SETTINGS.detector_save_path, save_file
            ))
        except (IOError, OSError):
            pass

    return output


def replace_with_copy(image, replacement_image=None):
    return replacement_image.copy() if replacement_image else image.copy()


def resize(image, size, method=None):
    if size != image.size:
        image = image.resize(
            size, resample=(method or SETTINGS.detector_resize_method)
        )

    return image


def threshold(image):  # pylint: disable=too-many-locals
    histogram = image.histogram()

    cum_sum = [0] * 256
    cum_sum_reversed = [0] * 256
    cum_integral = [0] * 256
    cum_integral_reversed = [0] * 256

    sum_total = image.size[0] * image.size[1]
    running_total = 0
    running_total_reversed = 0
    running_integral = 0
    running_integral_reversed = 0

    for idx, (num, num_reversed) in enumerate(zip(histogram, histogram[::-1])):
        delta = num / sum_total
        running_total += delta
        running_integral += delta * idx

        delta_reversed = num_reversed / sum_total
        running_total_reversed += delta_reversed
        running_integral_reversed += delta_reversed * (255 - idx)

        cum_sum[idx] = running_total
        cum_sum_reversed[255 - idx] = running_total_reversed

        cum_integral[idx] = running_integral
        cum_integral_reversed[255 - idx] = running_integral_reversed

    variance = [
        running_total * running_total_reversed * (
            (running_integral / running_total)
            - (running_integral_reversed / running_total_reversed)
        ) ** 2
        if running_total and running_total_reversed
        and running_integral and running_integral_reversed
        else 0
        for running_total, running_total_reversed,
        running_integral, running_integral_reversed in
        zip(cum_sum[:-1], cum_sum_reversed[1:],
            cum_integral[:-1], cum_integral_reversed[1:])
    ]

    target = max(variance)
    target = max([idx for idx, val in enumerate(variance) if val == target])  # pylint: disable=consider-using-generator
    target = target + 1

    image = image.point([255 if (i > target) else 0 for i in range(256)])

    return image


def trim_to_bounding_box(image):
    box = image.convert('1').getbbox()
    if not box:
        return image

    image = image.crop(box)

    return image
