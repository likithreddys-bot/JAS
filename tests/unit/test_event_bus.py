import threading

from app.core.events.bus import EventBus


class Ping:
    pass


class Pong:
    pass


def test_delivers_only_to_matching_type():
    bus = EventBus()
    got = []
    bus.subscribe(Ping, got.append)
    bus.publish(Pong())
    ping = Ping()
    bus.publish(ping)
    assert got == [ping]


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    got = []
    unsubscribe = bus.subscribe(Ping, got.append)
    unsubscribe()
    bus.publish(Ping())
    assert got == []


def test_failing_handler_does_not_block_others():
    bus = EventBus()
    got = []

    def broken(_):
        raise RuntimeError("boom")

    bus.subscribe(Ping, broken)
    bus.subscribe(Ping, got.append)
    bus.publish(Ping())
    assert len(got) == 1


def test_publish_from_many_threads():
    bus = EventBus()
    got = []
    lock = threading.Lock()

    def handler(e):
        with lock:
            got.append(e)

    bus.subscribe(Ping, handler)
    threads = [threading.Thread(target=lambda: [bus.publish(Ping()) for _ in range(100)]) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(got) == 800
