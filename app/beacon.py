"""So the phone can find this laptop without being told where it is.

The router hands out a new address every so often — in two days this laptop was 192.168.0.131, then
.118, then .111 — and an app you have to retype an IP into every morning is not an app that works.

The phone shouts "JAS?" across the local network and whatever laptop is running JAS answers with its
address. That is all. The reply carries no PIN, no name and no state: knowing where JAS lives gets
you nothing, because every real request still has to carry the PIN.

UDP broadcast rather than mDNS on purpose: mDNS needs a responder running and Android's support for
it is uneven, while a broadcast is a dozen lines and works on any home network. It answers rather
than announcing itself, so nothing is being shouted continuously when no phone is asking.
"""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable

log = logging.getLogger("jarvis.beacon")

DISCOVERY_PORT = 8771
ASK = b"JAS?"
MAX_DATAGRAM = 64  # a question this short needs no more; anything larger is not ours


class Beacon:
    """Answers "where is JAS?" on the local network, and nothing else."""

    def __init__(self, port: int, discovery_port: int = DISCOVERY_PORT,
                 host_lookup: Callable[[], str] | None = None) -> None:
        self._port = port          # the port the phone should actually talk to
        self._discovery = discovery_port
        self._socket: socket.socket | None = None
        self._thread = threading.Thread(target=self._serve, name="beacon", daemon=True)
        if host_lookup is None:
            from app.remote import local_host
            host_lookup = local_host
        self._host_lookup = host_lookup

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        sock, self._socket = self._socket, None
        if sock is not None:
            sock.close()

    @property
    def answer(self) -> bytes:
        # Looked up fresh on every reply, never cached: this laptop's address changed three times
        # in two days while JAS kept running, and a beacon that remembers where it *used* to be
        # sends the phone to an address nothing answers on any more.
        return f"JAS {self._host_lookup()} {self._port}".encode()

    def _serve(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._discovery))
        except OSError:
            # Another program has the port, or the firewall refused it. The phone can still be
            # given the address by hand, so this is a convenience lost, not a failure.
            log.warning("Could not listen for phones on UDP %d; they will need the address typed in",
                        self._discovery)
            return
        self._socket = sock
        log.info("Listening for phones looking for JAS on UDP %d", self._discovery)
        while self._socket is sock:
            try:
                question, where = sock.recvfrom(MAX_DATAGRAM)
            except OSError:
                return  # closed by stop(), or the network went away
            if question.strip().upper().startswith(ASK):
                try:
                    sock.sendto(self.answer, where)
                    log.info("Told %s where to find JAS", where[0])
                except OSError:
                    log.debug("Could not reply to %s", where[0])
