# -*- coding: utf-8 -*-
from datetime import date, datetime

import pytest

from watchtimer import WatchTimer
from player import UpNextPlayer
from state import State


def test_counts_active_time_across_episodes_without_pause_seek_or_buffering():
    timer = WatchTimer()
    timer.observe('a', 10, now=0)
    timer.observe('a', 11, now=1)
    timer.observe('a', 12, paused=True, now=2)
    timer.observe('a', 12, now=100)
    timer.observe('a', 200, now=101)
    timer.observe('a', 201, now=120)
    timer.observe('b', 0, now=121)
    timer.observe('b', 1, now=122)
    assert timer.elapsed == 2


def test_optional_timer_and_daily_bedtime():
    timer = WatchTimer()
    timer.elapsed = 3600
    before = datetime(2026, 11, 1, 22, 59)
    at = datetime(2026, 11, 1, 23, 0)
    tomorrow = datetime(2026, 11, 2, 23, 0)
    assert not timer.due(0, False, 23, 0, now=at)
    assert timer.due(60, False, 23, 0, now=before)
    assert not timer.due(0, True, 23, 0, now=before)
    assert timer.due(0, True, 23, 0, now=at)
    timer.reset(acknowledge_bedtime=True)
    assert timer.elapsed == 0
    assert not timer.due(0, True, 23, 0, now=at)
    assert timer.due(0, True, 23, 0, now=tomorrow)


def test_bedtime_stays_pending_if_episode_ends_after_midnight():
    timer = WatchTimer()
    timer.mark_bedtime(True, 23, 0, now=datetime(2026, 11, 1, 23, 30))
    after_midnight = datetime(2026, 11, 2, 0, 15)
    assert timer.due(0, True, 23, 0, now=after_midnight)
    timer.reset(acknowledge_bedtime=True)
    assert not timer.due(0, True, 23, 0, now=after_midnight)


@pytest.mark.parametrize('hour,minute,now,expected', [
    (0, 30, datetime(2026, 11, 1, 15, 0), False),
    (1, 0, datetime(2026, 11, 1, 20, 0), False),
    (23, 0, datetime(2026, 11, 2, 0, 15), True),
    (23, 0, datetime(2026, 11, 1, 23, 5), True),
    (0, 30, datetime(2026, 11, 2, 0, 29), False),
    (0, 30, datetime(2026, 11, 2, 0, 30), True),
    (0, 30, datetime(2026, 11, 2, 5, 59), True),
    (0, 30, datetime(2026, 11, 2, 6, 0), False),
    (23, 0, datetime(2026, 11, 2, 6, 0), False),
])
def test_bedtime_window(hour, minute, now, expected):
    assert WatchTimer().due(0, True, hour, minute, now=now) is expected


def test_acknowledgement_belongs_to_night_start_and_resets_next_night():
    timer = WatchTimer()
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 0, 15))
    assert timer.bedtime_pending == date(2026, 11, 1)
    timer.reset(acknowledge_bedtime=True)
    assert not timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 5, 59))
    assert not timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 6, 0))
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 23, 0))
    assert timer.bedtime_pending == date(2026, 11, 2)


def test_pending_bedtime_survives_morning_until_transition():
    timer = WatchTimer()
    timer.mark_bedtime(True, 23, 0, now=datetime(2026, 11, 2, 5, 59))
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 6, 1))
    assert timer.bedtime_pending == date(2026, 11, 1)


def test_pending_bedtime_is_updated_for_a_later_night():
    timer = WatchTimer()
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 1, 23, 0))
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 0, 15))
    assert timer.bedtime_pending == date(2026, 11, 1)
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 2, 23, 0))
    assert timer.bedtime_pending == date(2026, 11, 2)
    timer.reset(acknowledge_bedtime=True)
    assert not timer.due(0, True, 23, 0, now=datetime(2026, 11, 3, 0, 15))


def test_early_confirmation_does_not_acknowledge_later_bedtime():
    timer = WatchTimer()
    timer.reset(acknowledge_bedtime=True)
    assert timer.due(0, True, 23, 0, now=datetime(2026, 11, 1, 23, 0))


def test_natural_episode_transition_keeps_elapsed_time(monkeypatch):
    monkeypatch.setattr(State, '_shared_state', {})
    player = UpNextPlayer()
    player.reset_queue = lambda: None
    player.state.watch_timer.elapsed = 120
    player.state.playing_next = True
    player.onPlayBackEnded()
    assert player.state.watch_timer.elapsed == 120
