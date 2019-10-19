# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
''' Implements static functions used elsewhere in the add-on '''

from __future__ import absolute_import, division, unicode_literals


def to_unicode(text, encoding='utf-8'):
    ''' Force text to unicode '''
    return text.decode(encoding) if isinstance(text, bytes) else text


def from_unicode(text, encoding='utf-8'):
    ''' Force unicode to text '''
    import sys
    if sys.version_info.major == 2 and isinstance(text, unicode):  # noqa: F821; pylint: disable=undefined-variable
        return text.encode(encoding)
    return text
