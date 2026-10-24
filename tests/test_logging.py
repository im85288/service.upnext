# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

import pytest
import utils


@pytest.fixture
def logged(monkeypatch):
    lines = []

    def no_jsonrpc(**kwargs):
        raise AssertionError('log() must not make JSON-RPC calls')

    def no_property(*args, **kwargs):
        raise AssertionError('log() must not set window properties')

    monkeypatch.setattr(utils, 'jsonrpc', no_jsonrpc)
    monkeypatch.setattr(utils, 'set_property', no_property)
    monkeypatch.setattr(utils, 'xlog', lambda msg, level: lines.append((msg, level)))
    return lines


@pytest.mark.parametrize('log_level,debug,level,expected', [
    (0, False, 0, utils.LOGINFO),   # important messages always logged
    (0, False, 2, None),            # debug messages dropped at the default level
    (2, False, 2, utils.LOGINFO),   # debug messages logged when the add-on log level is Debug
    (0, True, 2, utils.LOGDEBUG),   # Kodi debug logging logs everything as debug
])
def test_log_level_without_json_rpc(monkeypatch, logged, log_level, debug, level, expected):
    monkeypatch.setattr(utils, 'get_setting_int', lambda key, default=None: log_level)
    monkeypatch.setattr(utils, 'getCondVisibility', lambda condition: debug)
    utils.log('message', name='Test', level=level)
    assert [line_level for _, line_level in logged] == ([expected] if expected is not None else [])
