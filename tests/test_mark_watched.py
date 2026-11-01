# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Marking a library episode as watched when Up Next moves on before Kodi counts it (issue #75)"""

import pytest
import api
import playbackmanager
import test_playbackmanager
from test_playbackmanager import Stub

run_popup = test_playbackmanager.run_popup  # share the popup fixture
DELAY = playbackmanager.WATCHED_CHECK_DELAY


class Library:
    """The watched state Kodi keeps for library episodes, and what Up Next changed"""

    def __init__(self, **episodes):
        self.episodes = {int(key[1:]): value for key, value in episodes.items()}  # e7=(playcount, resume)
        self.marked = []

    def get_watched_state(self, episodeid):
        return self.episodes.get(episodeid)

    def mark_watched(self, episodeid, playcount):
        self.marked.append((episodeid, playcount))
        self.episodes[episodeid] = (playcount, 0)


@pytest.fixture
def manager(monkeypatch):
    clock = {'now': 1000.0}
    settings = {'markWatchedEarly': True}
    playing = {'file': 'S01E07.mkv'}
    library = Library(e7=(0, 0), e8=(0, 0))

    def get_playing_file():
        if playing['file'] is None:
            raise RuntimeError('No active playback')
        return playing['file']

    monkeypatch.setattr(playbackmanager, 'monotonic', lambda: clock['now'])
    monkeypatch.setattr(playbackmanager, 'get_setting_bool', lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(playbackmanager, 'get_watched_state', library.get_watched_state)
    monkeypatch.setattr(playbackmanager, 'mark_watched', library.mark_watched)
    instance = object.__new__(playbackmanager.PlaybackManager)
    instance._watched_checks = []  # pylint: disable=protected-access
    instance.player = Stub(getPlayingFile=get_playing_file)
    instance.log = lambda *args, **kwargs: None
    instance.library, instance.clock, instance.settings, instance.playing = library, clock, settings, playing
    return instance


def tick(instance, seconds=1):
    """One pass of the service loop, a given time later"""
    instance.clock['now'] += seconds
    instance.check_previous_watched()


def move_on(instance, episodeid=7, kodi_saved=None, next_file='S01E08.mkv'):
    """Up Next starts the next episode, which then plays; Kodi saves the previous one's own state"""
    instance.remember_watched_state(episodeid, 'library')
    instance.playing['file'] = next_file
    if kodi_saved is not None:
        instance.library.episodes[episodeid] = kodi_saved
    tick(instance)
    tick(instance, DELAY)


def test_episode_left_early_is_marked_watched(manager):
    move_on(manager, kodi_saved=(0, 1250.0))  # Kodi kept a resume point and no play count
    assert manager.library.marked == [(7, 1)]
    assert manager.library.episodes[7] == (1, 0)


def test_rewatched_episode_left_early_counts_once_more(manager):
    manager.library.episodes[7] = (2, 0)
    move_on(manager, kodi_saved=(2, 1250.0))
    assert manager.library.marked == [(7, 3)]


def test_episode_kodi_counted_is_not_counted_twice(manager):
    move_on(manager, kodi_saved=(1, 0))
    assert manager.library.marked == []


def test_check_waits_for_kodi_to_save_the_previous_episode(manager):
    manager.remember_watched_state(7, 'library')
    manager.playing['file'] = 'S01E08.mkv'
    tick(manager)                 # the next episode is playing
    tick(manager, DELAY - 1)
    assert manager.library.marked == []
    tick(manager)
    assert manager.library.marked == [(7, 1)]
    tick(manager, 60)             # checked once only
    assert manager.library.marked == [(7, 1)]


def test_slow_next_episode_is_waited_for(manager):
    manager.remember_watched_state(7, 'library')
    manager.playing['file'] = None  # still opening
    tick(manager, 30)
    manager.playing['file'] = 'S01E08.mkv'
    tick(manager)
    tick(manager, DELAY)
    assert manager.library.marked == [(7, 1)]


@pytest.mark.parametrize('playing_after', ['S01E07.mkv', None])  # the old episode carries on, or playback ended
def test_failed_switch_leaves_the_episode_alone(manager, playing_after):
    manager.remember_watched_state(7, 'library')
    manager.playing['file'] = playing_after
    for _ in range(3):
        tick(manager, playbackmanager.WATCHED_SWITCH_TIMEOUT)
    manager.playing['file'] = 'S01E08.mkv'  # something else plays much later
    tick(manager)
    tick(manager, DELAY)
    assert manager.library.marked == []


def test_quick_transitions_each_get_checked(manager):
    # Watch Now on episode 7, then again on episode 8 before the first check is due
    manager.remember_watched_state(7, 'library')
    manager.playing['file'] = 'S01E08.mkv'
    tick(manager)
    manager.remember_watched_state(8, 'library')
    manager.playing['file'] = 'S01E09.mkv'
    tick(manager)
    tick(manager, DELAY)
    assert sorted(manager.library.marked) == [(7, 1), (8, 1)]


def test_overdue_check_survives_a_popup(manager):
    # A short episode's popup blocks the service loop past the first check's time
    manager.remember_watched_state(7, 'library')
    manager.playing['file'] = 'S01E08.mkv'
    tick(manager)
    manager.clock['now'] += 3 * DELAY
    manager.remember_watched_state(8, 'library')
    manager.playing['file'] = 'S01E09.mkv'
    tick(manager)
    assert manager.library.marked == [(7, 1)]
    tick(manager, DELAY)
    assert manager.library.marked == [(7, 1), (8, 1)]


@pytest.mark.parametrize('episodeid', [None, 0, -1, 99])  # not identified, or not in the library
def test_unknown_episodes_are_left_alone(manager, episodeid):
    move_on(manager, episodeid=episodeid)
    assert manager.library.marked == []


@pytest.mark.parametrize('source', ['addon', 'playlist'])
def test_only_library_episodes_are_checked(manager, source):
    """Add-on episodes keep their watched state in the add-on; playlist items have no library lookup"""
    manager.remember_watched_state(7, source)
    manager.playing['file'] = 'S01E08.mkv'
    tick(manager)
    tick(manager, DELAY)
    assert manager.library.marked == []


def test_setting_off_leaves_kodi_to_decide(manager):
    manager.settings['markWatchedEarly'] = False
    move_on(manager)
    assert manager.library.marked == []


@pytest.mark.parametrize('action,remembered', [('watch', True), ('timeout', True), ('stop', False), ('back', False)])
def test_library_episode_is_remembered_only_when_moving_on(monkeypatch, run_popup, action, remembered):
    calls = []
    monkeypatch.setattr(playbackmanager.PlaybackManager, 'remember_watched_state',
                        lambda self, episodeid, source: calls.append((episodeid, source)))
    run_popup(action=action, source='library')
    assert calls == ([('current', 'library')] if remembered else [])


def test_watched_state_json_rpc(monkeypatch):
    calls = []

    def jsonrpc(method, params):
        calls.append((method, params))
        if params['episodeid'] == 99:
            return {'error': {'code': -32602}}
        return {'result': {'episodedetails': {'playcount': 2, 'resume': {'position': 1250.0, 'total': 1800.0}}}}

    monkeypatch.setattr(api, 'jsonrpc', jsonrpc)
    assert api.get_watched_state(7) == (2, 1250.0)
    assert api.get_watched_state(99) is None
    api.mark_watched(7, 3)
    assert calls[-1] == ('VideoLibrary.SetEpisodeDetails',
                         {'episodeid': 7, 'playcount': 3, 'resume': {'position': 0, 'total': 0}})
