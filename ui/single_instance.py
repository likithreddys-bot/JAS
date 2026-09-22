"""Lets a second launch of JARVIS ask the running one to show itself, then exit."""
from __future__ import annotations

import getpass

from PySide6.QtCore import Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = f"jarvis-{getpass.getuser()}"


def notify_running_instance() -> bool:
    """Ask an already-running JARVIS to show its window. Returns True if one answered."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


class InstanceServer(QLocalServer):
    showRequested = Signal()

    def listen_for_launches(self) -> bool:
        QLocalServer.removeServer(SERVER_NAME)  # clear a stale name left by a crash
        self.newConnection.connect(self._on_connection)
        return self.listen(SERVER_NAME)

    def _on_connection(self) -> None:
        socket = self.nextPendingConnection()
        socket.readyRead.connect(lambda: self._on_message(socket))

    def _on_message(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).strip() == b"show":
            self.showRequested.emit()
        socket.disconnectFromServer()
