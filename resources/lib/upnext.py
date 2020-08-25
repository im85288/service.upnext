# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from utils import event


def send_signal(sender, next_info):
    """Helper function for plugins to send up next data to UpNext"""
    event(sender=sender + '.SIGNAL', message='upnext_data', data=next_info, encoding='base64')
