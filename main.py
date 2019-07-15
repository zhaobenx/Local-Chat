# -*- coding: utf-8 -*-
"""
Created on 2019-07-10 18:27:27
@Author: ZHAO Lingfeng
@Version : 0.0.2
"""
import socket
import time
import threading
import struct
from dataclasses import dataclass
from collections import OrderedDict
from queue import Queue
import datetime
import random
import logging
from uuid import uuid4
import base64

import zmq

logger = logging.getLogger()

handler1 = logging.FileHandler("log.txt", encoding="utf-8")
handler2 = logging.FileHandler("debug-log.txt", encoding="utf-8")

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
BROADCAST_HEADER = b'LCBcMsg;'


@dataclass
class ChatInfo:
    
    ip: str
    port: int
    version: int
    timestamp: float = datetime.datetime.now().timestamp()

    def update(self):
        """Update timestamp to now
        """
        ts = datetime.datetime.now().timestamp()
        self.timestamp = ts if ts > self.timestamp else self.timestamp

    def outdated(self, timeout):
        """Return if timestamp outdated
        
        Args:
            timeout (number): timeout in seconds
        
        Returns:
            bool: True if outdated
        """
        ts = datetime.datetime.now().timestamp()
        if self.timestamp + timeout < ts:
            return True
        else:
            return False


class ChatListManager:

    PACK_FORMAT = '!HH4s'

    def __init__(self, tcp_port, version, timeout=20):
        """Use UDP to discovery local chat client
        
        Args:
            tcp_port (short): TCP port for chat client
            version (short): version identifier
            timeout (int, optional): seconds of chat info saves. Defaults to 20.
        """
        self.timeout = timeout
        self.peer_list = {}  # OrderedDict()
        # 4 digit is enough for LAN
        _uuid = uuid4().bytes[-4:]
        self.uuid = decode_uuid(_uuid)

        self.BROADCAST_MESSAGE = BROADCAST_HEADER + struct.pack(self.PACK_FORMAT, tcp_port, version, _uuid)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.run_c = threading.Thread(target=self._run_client)
        self.run_c.daemon = True

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('', UDP_PORT))
        self.run_s = threading.Thread(target=self._run_server)
        self.run_s.daemon = True

    def update_peer_list(self, uuid, chat_info: ChatInfo):
        if uuid in self.peer_list:
            self.peer_list[uuid].update()
        else:
            self.peer_list[uuid] = chat_info

        # safe delete timeout client
        d = {k: v for k, v in self.peer_list.items() if not v.outdated(self.timeout)}
        self.peer_list = d

    def get_list(self):
        """Return the peer list
        
        Returns:
            List[ChatInfo]: peer list
        """
        return self.peer_list

    def start(self):
        """Start this server(nonblock)
        """
        self.run_c.start()
        self.run_s.start()

    def _run_client(self):
        linfo('client started')

        while True:
            ldebug('UDP broadcast')
            self.client.sendto(self.BROADCAST_MESSAGE, (BROADCAST_ADDR, UDP_PORT))
            time.sleep(10)

    def _run_server(self):
        linfo('server started')
        while True:
            data, address = self.server.recvfrom(1024)
            ldebug(f"UDP received message: {data}, from {address}")
            if not data:
                lerror("Wrong ")
            if data.startswith(BROADCAST_HEADER):
                tcp_port, version, uuid = struct.unpack_from(self.PACK_FORMAT, data, len(BROADCAST_HEADER))
                uuid = decode_uuid(uuid)
                # print(tcp_port, version, address[0])
                self.update_peer_list(uuid, ChatInfo(address[0], tcp_port, version))


def decode_uuid(uuid):
    """make uuid human readable
    
    Args:
        uuid (bytes): uuid
    
    Returns:
        str: base32 encoded human readable string
    """
    return base64.b32encode(uuid).decode().replace('=', '').lower()


class ChatManager:
    # pylint: disable=no-member
    # TODO: clean useless socket in zclients
    def __init__(self):
        self.zcontext = zmq.Context()
        self.zserver = self.zcontext.socket(zmq.PULL)
        self.port = self.zserver.bind_to_random_port('tcp://*')
        self.clm = ChatListManager(self.port, VERSION)
        self.uuid = self.clm.uuid

        self.run_r = threading.Thread(target=self._receive_worker)
        self.run_r.daemon = True
        self.run_s = threading.Thread(target=self._send_worker)
        self.run_s.daemon = True

        self.zclients = {}
        self.send_queue = Queue()
        self.recv_queue = Queue()

    def _receive_worker(self):
        linfo(f'TCP server works on -{self.port}-')
        while True:
            msg = self.zserver.recv()
            # self.recv_queue.put(msg)
            print(f'$MESSAGE received: {msg}')

    def _send_worker(self):
        ldebug('send worker starts')
        while True:
            msg = self.send_queue.get()
            if msg is None:
                lwarning('Get None in send worder')
                continue
            uuid, message = msg
            if uuid not in self.clm.get_list():
                print(f'Invalid uuid {uuid}')
                if uuid in self.zclients:
                    self.zclients.pop(uuid)
                continue

            if uuid not in self.zclients:
                chat_info = self.get_chat_info(uuid)
                if chat_info is None:
                    print(f'Failed to send message to {uuid}, peer does not exists')
                    continue
                client = self.zcontext.socket(zmq.PUSH)
                client.connect(f'tcp://{chat_info.ip}:{chat_info.port}')
                self.zclients[uuid] = client
            self.zclients[uuid].send(message)

    def get_chat_info(self, uuid):
        return self.clm.get_list().get(uuid)

    def get_chat_list(self):
        return self.clm.get_list()

    def send_message(self, uuid, message):
        self.send_queue.put((uuid, message))  

    def start(self):
        self.clm.start()
        self.run_r.start()
        self.run_s.start()
        print(f'Name of this client is {self.uuid}')
        print('Chat starts')

    def run_test(self):
        self.clm.start()
        self.run_r.start()

        print(f'Name of this client is {self.uuid}')
        while True:
            ldebug('sending greatings')
            peer_list = self.clm.get_list()
            ldebug(f'peer list: {peer_list}')
            for c in peer_list:
                if c.uuid == self.uuid:
                    continue
                if c not in self.zclients:
                    client = self.zcontext.socket(zmq.PUSH)
                    client.connect(f'tcp://{c.ip}:{c.port}')
                    self.zclients[c] = client

                self.zclients[c].send_string(f'Hello from {self.uuid}|{self.port} to {c.uuid}|{c.ip}:{c.port}')
            time.sleep(10)


def main():
    cm = ChatManager()
    cm.start()
    while True:
        print(cm.get_chat_list())
        uuid = input("uuid:")
        message = input("Message:").encode()
        cm.send_message(uuid, message)


if __name__ == "__main__":
    main()
