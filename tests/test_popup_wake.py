# -*- coding: utf-8 -*-
"""Wake recovery for an already-open popup."""
from types import SimpleNamespace

import pytest
import playbackmanager


@pytest.mark.parametrize("kind", ["next", "still"])
def test_hidden_active_popup_reopens_after_wake(monkeypatch, kind):
    manager = object.__new__(playbackmanager.PlaybackManager)
    manager._popup_wake_pending = False
    shown = []
    page = SimpleNamespace(playback_dialog_id=13001, show=lambda: shown.append(kind))
    monkeypatch.setattr(playbackmanager, "getCondVisibility", lambda _: False)
    manager.request_popup_wake()
    manager.restore_popup_after_wake(page)
    manager.restore_popup_after_wake(page)
    assert shown == [kind]
    assert not manager._popup_wake_pending


def test_visible_popup_is_not_opened_twice(monkeypatch):
    manager = object.__new__(playbackmanager.PlaybackManager)
    shown = []
    page = SimpleNamespace(playback_dialog_id=13001, show=lambda: shown.append(True))
    monkeypatch.setattr(playbackmanager, "getCondVisibility", lambda condition: condition == "Window.IsVisible(13001)")
    manager.request_popup_wake()
    manager.restore_popup_after_wake(page)
    assert shown == [] and not manager._popup_wake_pending


def test_wake_waits_for_player_controls_to_close(monkeypatch):
    manager = object.__new__(playbackmanager.PlaybackManager)
    visible = {"Window.IsVisible(videoosd)": True, "Window.IsVisible(13001)": False}
    shown = []
    page = SimpleNamespace(playback_dialog_id=13001, show=lambda: shown.append(True))
    monkeypatch.setattr(playbackmanager, "getCondVisibility", visible.__getitem__)
    manager.request_popup_wake()
    manager.restore_popup_after_wake(page)
    assert shown == [] and manager._popup_wake_pending
    visible["Window.IsVisible(videoosd)"] = False
    manager.restore_popup_after_wake(page)
    assert shown == [True] and not manager._popup_wake_pending


def test_popup_waits_for_valid_dialog_identifier(monkeypatch):
    manager = object.__new__(playbackmanager.PlaybackManager)
    shown = []
    page = SimpleNamespace(playback_dialog_id=None, show=lambda: shown.append(True))
    monkeypatch.setattr(playbackmanager, "getCondVisibility", lambda _: False)
    manager.request_popup_wake()
    manager.restore_popup_after_wake(page)
    assert shown == [] and manager._popup_wake_pending
    page.playback_dialog_id = 13001
    manager.restore_popup_after_wake(page)
    assert shown == [True] and not manager._popup_wake_pending
