import pickle
import pprint
import queue
import sys
import threading
import zmq

import logging.config

from driver import LoRaHatDriver
from loraconfig import lora_hat_config, logging_config_dict
from message import TimeOrientPosMessage, DeserializeError

logging.config.dictConfig(logging_config_dict)


socket_name = "tcp://127.0.0.1:5555"

q = queue.Queue(maxsize=3)


def write_to_zeromq(socket_name):
    logging.info(f"binding to {socket_name} for zeroMQ IPC")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    with socket.connect(socket_name):
        logging.info("connected to zeroMQ IPC socket")

        while True:
            message = q.get()
            try:
                print(TimeOrientPosMessage.from_bytes(message))
            except DeserializeError as e:
                logging.error(e)


threading.Thread(target=write_to_zeromq, daemon=True, args=[socket_name]).start()

with LoRaHatDriver(lora_hat_config) as lora_hat:
    logging.debug(f"LoRa hat config: {pprint.pformat(lora_hat.config)}")
    while True:
        q.put(lora_hat.receive(), block=False)
