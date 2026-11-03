# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Continuing a partly watched next episode at its resume point when Up Next plays it"""

import pytest
import playbackmanager
import test_playbackmanager
from test_playbackmanager import Stub

run_popup = test_playbackmanager.run_popup  # share the popup fixture
NEXT = {'episodeid': 8, 'resume': {'position': 1250.0, 'total': 1800.0}}


@pytest.fixture
def manager(monkeypatch):
    clock = {'now': 1000.0}
    settings = {'resumeNextEpisode': True}
    playing = {'episode': 7, 'time': 600.0}
    seeks = []

    def get_time():
        if playing['episode'] is None:
            raise RuntimeError('No active playback')
        return playing['time']

    monkeypatch.setattr(playbackmanager, 'monotonic', lambda: clock['now'])
    monkeypatch.setattr(playbackmanager, 'get_setting_bool', lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(playbackmanager, 'playing_episode_id', lambda: playing['episode'])
    instance = object.__new__(playbackmanager.PlaybackManager)
    instance._pending_resume = None  # pylint: disable=protected-access
    instance.state = Stub(current_episode_id=7)
    instance.player = Stub(getTime=get_time, seekTime=seeks.append)
    instance.log = lambda *args, **kwargs: None
    instance.clock, instance.settings, instance.playing, instance.seeks = clock, settings, playing, seeks
    return instance


def tick(instance, seconds=1):
    """One pass of the service loop, a given time later"""
    instance.clock['now'] += seconds
    instance.resume_next_episode()


def start(instance, episode=8, time=0.5):
    instance.playing['episode'], instance.playing['time'] = episode, time


def test_partly_watched_next_episode_resumes(manager):
    manager.remember_resume_point(NEXT, 'library')
    tick(manager)                 # the previous episode is still playing
    start(manager)
    tick(manager)
    assert manager.seeks == [1250.0]
    tick(manager, 5)              # once only, even if the viewer goes back to the start
    start(manager, time=3)
    tick(manager)
    assert manager.seeks == [1250.0]


def test_slow_start_is_waited_for(manager):
    manager.remember_resume_point(NEXT, 'library')
    start(manager, episode=None)  # still opening, or no item details yet
    tick(manager, 30)
    start(manager)
    tick(manager)
    assert manager.seeks == [1250.0]


def test_already_resumed_by_kodi_is_left_alone(manager):
    manager.remember_resume_point(NEXT, 'library')
    start(manager, time=1251.0)
    tick(manager)
    assert manager.seeks == []
    assert manager._pending_resume is None  # pylint: disable=protected-access


@pytest.mark.parametrize('episode', [9, -1])  # another library episode, or something else
def test_other_video_is_not_moved(manager, episode):
    manager.remember_resume_point(NEXT, 'library')
    start(manager, episode=episode)
    tick(manager)
    start(manager)                # the next episode played much later
    tick(manager)
    assert manager.seeks == []


def test_next_episode_that_never_starts_is_forgotten(manager):
    manager.remember_resume_point(NEXT, 'library')
    start(manager, episode=None)
    tick(manager, playbackmanager.WATCHED_SWITCH_TIMEOUT + 1)
    start(manager)
    tick(manager)
    assert manager.seeks == []


@pytest.mark.parametrize('episode', [
    {'episodeid': 8, 'resume': {'position': 0, 'total': 0}},   # not started
    {'episodeid': 8},                                          # no resume details
    {'episodeid': -1, 'resume': NEXT['resume']},               # not in the library
])
def test_nothing_to_resume(manager, episode):
    manager.remember_resume_point(episode, 'library')
    start(manager)
    tick(manager)
    assert manager.seeks == []


@pytest.mark.parametrize('source', ['addon', 'playlist'])
def test_only_library_episodes_are_resumed(manager, source):
    """Add-ons decide where their own items start; playlist items have no library details"""
    manager.remember_resume_point(NEXT, source)
    start(manager)
    tick(manager)
    assert manager.seeks == []


def test_setting_off_starts_from_the_beginning(manager):
    manager.settings['resumeNextEpisode'] = False
    manager.remember_resume_point(NEXT, 'library')
    start(manager)
    tick(manager)
    assert manager.seeks == []


def test_seek_failure_is_logged_not_raised(manager):
    def fail(seconds):
        raise RuntimeError('Kodi is not playing any media file')

    manager.player.seekTime = fail
    manager.remember_resume_point(NEXT, 'library')
    start(manager)
    tick(manager)                 # no exception


@pytest.mark.parametrize('action,remembered', [('watch', True), ('timeout', True), ('stop', False), ('back', False)])
def test_resume_point_is_remembered_only_when_moving_on(monkeypatch, run_popup, action, remembered):
    calls = []
    monkeypatch.setattr(playbackmanager.PlaybackManager, 'remember_watched_state', lambda *args: None)
    monkeypatch.setattr(playbackmanager.PlaybackManager, 'remember_resume_point',
                        lambda self, episode, source: calls.append((episode['episodeid'], source)))
    run_popup(action=action, source='library')
    assert calls == ([('next', 'library')] if remembered else [])
