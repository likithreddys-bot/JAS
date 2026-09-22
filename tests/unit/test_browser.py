import json

import pytest

from app.tools import media
from app.tools.browser import browser_tools, chrome_profiles, music


@pytest.fixture
def user_data(tmp_path):
    state = {"profile": {"last_used": "Profile 2", "info_cache": {
        "Profile 2": {"name": "likithreddy", "user_name": "likith@example.com"},
        "Profile 3": {"name": "vaibhav-vyapaar.com", "user_name": "work@vaibhav-vyapaar.com"},
        "Profile 4": {"name": "Likith", "user_name": ""},
        "Profile 5": {"name": "TheBatMan", "user_name": ""},
        "Profile 6": {"name": "Jaya", "user_name": ""},
    }}}
    (tmp_path / "Local State").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def test_profiles_are_listed_with_last_used(user_data):
    profiles, last_used = chrome_profiles.list_profiles(user_data)
    assert [p.name for p in profiles] == ["likithreddy", "vaibhav-vyapaar.com", "Likith", "TheBatMan", "Jaya"]
    assert last_used == "Profile 2"


@pytest.mark.parametrize("spoken, directory", [
    ("Likith", "Profile 4"),  # exact name beats the similar "likithreddy"
    ("likithreddy", "Profile 2"),
    ("batman", "Profile 5"),
    ("jaya", "Profile 6"),
    ("vaibhav", "Profile 3"),
    ("work@vaibhav-vyapaar.com", "Profile 3"),
])
def test_spoken_profile_names_match(user_data, spoken, directory):
    profiles, _ = chrome_profiles.list_profiles(user_data)
    assert chrome_profiles.find_profile(spoken, profiles).directory == directory


def test_unknown_profile_is_not_guessed(user_data):
    profiles, _ = chrome_profiles.list_profiles(user_data)
    assert chrome_profiles.find_profile("superman", profiles) is None


@pytest.mark.parametrize("url, expected", [
    ("gmail.com", "https://gmail.com"),
    ("https://music.youtube.com", "https://music.youtube.com"),
    ("  youtube.com  ", "https://youtube.com"),
])
def test_urls_get_a_scheme(url, expected):
    assert chrome_profiles.normalize_url(url) == expected


def test_default_profile_setting_is_used(user_data, monkeypatch):
    monkeypatch.setattr(chrome_profiles, "USER_DATA", user_data)
    monkeypatch.setattr(chrome_profiles, "list_profiles", lambda user_data=user_data: _real_list(user_data))
    assert chrome_profiles.pick("", "")[0].name == "likithreddy"  # last used
    assert chrome_profiles.pick("", "Jaya")[0].name == "Jaya"  # configured default
    assert chrome_profiles.pick("batman", "Jaya")[0].name == "TheBatMan"  # named in the request wins
    profile, error = chrome_profiles.pick("superman", "")
    assert profile is None and "TheBatMan" in error


_real_list = chrome_profiles.list_profiles


def test_titles_match_and_relevance():
    assert media.titles_match("Sahiba", "Sahiba")
    assert media.titles_match("Tum Hi Ho", "Tum Hi Ho (From Aashiqui 2)")
    assert not media.titles_match("Sahiba", "New Horlicks Milkshake")
    assert music.relevant("tum jo aaye", "Tum Jo Aaye (Lyrics) - Rahat Fateh Ali Khan")
    assert not music.relevant("zzqqxxnotasongqq", "Tum Jo Aaye (Lyrics) - Rahat Fateh Ali Khan")


def test_search_redirects_are_unwrapped():
    from app.tools.browser.session import _unwrap_redirect

    assert _unwrap_redirect("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FCharminar&rut=x") \
        == "https://en.wikipedia.org/wiki/Charminar"
    assert _unwrap_redirect("https://example.com/page") == "https://example.com/page"


@pytest.fixture
def fake_play(monkeypatch, user_data):
    """play_music with the network, Chrome and Windows media controls faked out."""
    opened = []
    monkeypatch.setattr(chrome_profiles, "list_profiles", lambda user_data=user_data: _real_list(user_data))
    monkeypatch.setattr(chrome_profiles, "open_profile", lambda profile, url: opened.append((profile.name, url)) or object())
    monkeypatch.setattr(music, "find_song", lambda q: music.Track("Sahiba", "Aditya Rikhari", "https://music.youtube.com/watch?v=x"))
    playing = {"state": media.NowPlaying("Chrome", "Sahiba", "Aditya Rikhari", True)}
    monkeypatch.setattr(media, "wait_until_playing", lambda title: playing["state"])
    tools = {t.name: t for t in browser_tools(session=None, default_profile="Likith")}
    return tools["play_music"], opened, playing


def test_music_plays_in_the_users_default_profile(fake_play):
    play, opened, _ = fake_play
    result = play.run(query="Sahiba")
    assert result.ok and result.data["title"] == "Sahiba" and result.data["profile"] == "Likith"
    assert opened == [("Likith", "https://music.youtube.com/watch?v=x")]


def test_music_reports_ads_and_failures_honestly(fake_play):
    play, _, playing = fake_play
    playing["state"] = media.NowPlaying("Chrome", "Horlicks Milkshake", "", True)
    result = play.run(query="Sahiba")
    assert result.ok and "ad" in result.data["note"]
    playing["state"] = None
    result = play.run(query="Sahiba")
    assert not result.ok and "didn't start playing" in result.error
