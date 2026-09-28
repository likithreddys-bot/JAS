"""The beacon that lets the phone find this laptop after the router moves it."""
import socket
import time

import pytest

from app.beacon import Beacon


@pytest.fixture
def beacon():
    """On a port of its own, so a running JAS on 8771 does not answer these tests instead."""
    started = Beacon(8770, discovery_port=8897, host_lookup=lambda: "192.168.0.111")
    started.start()
    time.sleep(0.3)
    yield started
    started.stop()


def ask(question, port=8897, timeout=1.5):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(question, ("255.255.255.255", port))
        return sock.recvfrom(64)[0]
    except socket.timeout:
        return None
    finally:
        sock.close()


def test_it_tells_a_phone_where_jas_is(beacon):
    """The router gave this laptop three addresses in two days, so the phone must ask, not remember."""
    assert ask(b"JAS?") == b"JAS 192.168.0.111 8770"


def test_it_ignores_anything_that_is_not_asking_for_jas(beacon):
    """Something else broadcasting on this port must not get an answer."""
    assert ask(b"who is there?") is None


def test_the_answer_carries_no_secret(beacon):
    """Finding JAS must grant nothing: the PIN guards every real request."""
    answer = ask(b"JAS?").decode()
    assert "173407" not in answer
    assert answer.split() == ["JAS", "192.168.0.111", "8770"], "address and port, nothing else"


def test_a_taken_port_is_survivable():
    """If the firewall or another program has the port, the address can still be typed in."""
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("", 8896))
    try:
        quiet = Beacon(8770, discovery_port=8896, host_lookup=lambda: "192.168.0.111")
        quiet.start()
        time.sleep(0.3)
        quiet.stop()  # the point is that starting it did not raise
    finally:
        blocker.close()


def test_the_answer_reflects_the_current_address_not_a_cached_one():
    """The router changed this laptop's address three times in two days while JAS kept running.

    A beacon that remembers where it *used to be* sends the phone to an address nothing answers
    on any more - exactly the bug this caught: the phone was told "192.168.0.111" when the laptop
    had moved to "192.168.0.109" hours earlier, without JAS ever having been restarted.
    """
    current = ["192.168.0.111"]
    live = Beacon(8770, discovery_port=8898, host_lookup=lambda: current[0])
    live.start()
    time.sleep(0.3)
    try:
        assert ask(b"JAS?", port=8898) == b"JAS 192.168.0.111 8770"
        current[0] = "192.168.0.109"  # the router reassigned it; JAS itself never restarted
        assert ask(b"JAS?", port=8898) == b"JAS 192.168.0.109 8770",             "the beacon must look the address up again, not repeat what it said last time"
    finally:
        live.stop()
