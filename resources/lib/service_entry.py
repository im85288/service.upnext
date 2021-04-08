# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the UpNext service entry point"""

from __future__ import absolute_import, division, unicode_literals
import monitor


# Start the monitor and wait indefinitely for abort
monitor.UpNextMonitor().start()
