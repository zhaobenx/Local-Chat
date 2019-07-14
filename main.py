# -*- coding: utf-8 -*-
"""
Created on 2019-07-10 18:27:27
@Author: ZHAO Lingfeng
@Version : 0.0.1
"""
import socket
import time
import threading
import struct
from dataclasses import dataclass
from collections import OrderedDict
from queue import deque
import datetime
import random
import logging

logger = logging.getLogger()

handler1 = logging.FileHandler("log.txt", encoding="utf-8")
handler2 = logging.StreamHandler()

logger.setLevel(level=logging.NOTSET)
handler1.setLevel(logging.INFO)
handler2.setLevel(logging.DEBUG)

formatter1 = logging.Formatter('%(asctime)s %(filename)s:%(levelname)s:%(message)s')
handler1.setFormatter(formatter1)
formatter2 = logging.Formatter('%(filename)s:%(lineno)d:%(message)s')
handler2.setFormatter(formatter2)

logger.addHandler(handler1)
logger.addHandler(handler2)

ldebug = logger.debug
linfo = logger.info
lwarning = logger.warning
lerror = logger.error
lcritical = logger.critical

# Code starts:
VERSION = 1

UDP_PORT = 23456
BROADCAST_ADDR = '255.255.255.255'
BROADCAST_HEADER = b'LocalChatBcMsg;'


@dataclass(frozen=True, eq=True)
class ChatList:
    ip: str
    port: int
    version: int


class ChatListManager:

    PACK_FORMAT = '!HH'

    def __init__(self, tcp_port, version, timeout=20):
        self.timeout = timeout
        self.peer_list = {}  # OrderedDict()

        self.BROADCAST_MESSAGE = BROADCAST_HEADER + struct.pack(self.PACK_FORMAT, tcp_port, version)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.run_c = threading.Thread(target=self.run_client)
        self.run_c.daemon = True

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('', UDP_PORT))
        self.run_s = threading.Thread(target=self.run_server)
        self.run_s.daemon = True

    def update_peer_list(self, chat_list: ChatList):
        if chat_list in self.peer_list:
            if self.peer_list[chat_list] < datetime.datetime.now().timestamp():
                self.peer_list[chat_list] = datetime.datetime.now().timestamp()
        else:
            self.peer_list[chat_list] = datetime.datetime.now().timestamp()
        # safe delete timeout client
        d = {k: v for k, v in self.peer_list.items() if v + self.timeout > datetime.datetime.now().timestamp()}
        self.peer_list = d

    def get_list(self):
        return [k for k, v in self.peer_list.items() if v + self.timeout > datetime.datetime.now().timestamp()]

    def run(self):
        self.run_c.start()
        self.run_s.start()

    def run_client(self):
        linfo('client started')

        while True:
            ldebug('UDP broadcast')
            self.client.sendto(self.BROADCAST_MESSAGE, (BROADCAST_ADDR, UDP_PORT))
            time.sleep(10)

    def run_server(self):
        linfo('server started')
        while True:
            data, address = self.server.recvfrom(1024)
            ldebug(f"UDP received message: {data}, from {address}")
            if not data:
                lerror("Wrong ")
            if data.startswith(BROADCAST_HEADER):
                tcp_port, version = struct.unpack_from(self.PACK_FORMAT, data, len(BROADCAST_HEADER))
                # print(tcp_port, version, address[0])
                self.update_peer_list(ChatList(address[0], tcp_port, version))


def main():
    cm = ChatListManager(random.randrange(200, 20000), VERSION)
    cm.run()
    while 1:
        time.sleep(5)
        ldebug(f"== {cm.get_list()}")


if __name__ == "__main__":
    main()
