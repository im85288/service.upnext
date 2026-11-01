# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Marking a library episode as watched when Up Next moves on before Kodi counts it (issue #75)"""

import pytest
import playbackmanager
import test_playbackmanager

run_popup = test_playbackmanager.run_popup  # share the popup fixture


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
    monkeypatch.setattr(playbackmanager, 'monotonic', lambda: clock['now'])
    monkeypatch.setattr(playbackmanager, 'get_setting_bool', lambda key, default=None: settings.get(key, default))
    library = Library(e7=(0, 0))
    monkeypatch.setattr(playbackmanager, 'get_watched_state', library.get_watched_state)
    monkeypatch.setattr(playbackmanager, 'mark_watched', library.mark_watched)
    instance = object.__new__(playbackmanager.PlaybackManager)
    instance.api = library
    instance._watched_check = None  # pylint: disable=protected-access
    instance.log = lambda *args, **kwargs: None
    instance.clock = clock
    instance.settings = settings
    return instance


def move_on(instance, episodeid=7, kodi_saved=None):
    """Up Next starts the next episode; Kodi then saves the previous one's own state"""
    instance.remember_watched_state(episodeid, 'library')
    if kodi_saved is not None:
        instance.api.episodes[episodeid] = kodi_saved
    instance.clock['now'] += playbackmanager.WATCHED_CHECK_DELAY
    instance.check_previous_watched()


def test_episode_left_early_is_marked_watched(manager):
    move_on(manager, kodi_saved=(0, 1250.0))  # Kodi kept a resume point and no play count
    assert manager.api.marked == [(7, 1)]
    assert manager.api.episodes[7] == (1, 0)


def test_rewatched_episode_left_early_counts_once_more(manager):
    manager.api.episodes[7] = (2, 0)
    move_on(manager, kodi_saved=(2, 1250.0))
    assert manager.api.marked == [(7, 3)]


def test_episode_kodi_counted_is_not_counted_twice(manager):
    move_on(manager, kodi_saved=(1, 0))
    assert manager.api.marked == []


def test_check_waits_for_kodi_to_save_the_previous_episode(manager):
    manager.remember_watched_state(7, 'library')
    manager.clock['now'] += playbackmanager.WATCHED_CHECK_DELAY - 1
    manager.check_previous_watched()
    assert manager.api.marked == []
    manager.clock['now'] += 1
    manager.check_previous_watched()
    assert manager.api.marked == [(7, 1)]
    manager.clock['now'] += 60
    manager.check_previous_watched()  # checked once only
    assert manager.api.marked == [(7, 1)]


@pytest.mark.parametrize('episodeid', [None, 0, -1, 99])  # not identified, or not in the library
def test_unknown_episodes_are_left_alone(manager, episodeid):
    move_on(manager, episodeid=episodeid)
    assert manager.api.marked == []


def test_setting_off_leaves_kodi_to_decide(manager):
    manager.settings['markWatchedEarly'] = False
    move_on(manager)
    assert manager.api.marked == []


@pytest.mark.parametrize('source', ['addon', 'playlist'])
def test_only_library_episodes_are_checked(manager, source):
    """Add-on episodes keep their watched state in the add-on; playlist items have no library lookup"""
    manager.remember_watched_state(7, source)
    manager.clock['now'] += playbackmanager.WATCHED_CHECK_DELAY
    manager.check_previous_watched()
    assert manager.api.marked == []


@pytest.mark.parametrize('action,remembered', [('watch', True), ('timeout', True), ('stop', False), ('back', False)])
def test_library_episode_is_remembered_only_when_moving_on(monkeypatch, run_popup, action, remembered):
    calls = []
    monkeypatch.setattr(playbackmanager.PlaybackManager, 'remember_watched_state',
                        lambda self, episodeid, source: calls.append((episodeid, source)))
    run_popup(action=action, source='library')
    assert calls == ([('current', 'library')] if remembered else [])


def test_watched_state_json_rpc(monkeypatch):
    import api
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
