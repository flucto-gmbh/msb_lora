import itertools
import time
import pickle

import zmq
import numpy as np

from datetime import datetime

import logging.config

from loraconfig import logging_config_dict
from message import TimeOrientPosMessage, Topic

logging.config.dictConfig(logging_config_dict)


socket_name = "tcp://127.0.0.1:5555"

logging.info(f"binding to {socket_name} for zeroMQ IPC")
context = zmq.Context()
socket = context.socket(zmq.PUB)
with socket.connect(socket_name):
    logging.info("connected to zeroMQ IPC socket")
    sender_iter = itertools.cycle([150, 151, 153])
    while True:
        data = np.empty(8, dtype=TimeOrientPosMessage.array_dtype)
        data[0] = datetime.utcnow().timestamp()
        data[1:] = np.random.standard_normal(7)
        sender = next(sender_iter)
        message = TimeOrientPosMessage(data, sender, topic=Topic.ATTITUDE)
        data_dict = {
            "time": str(message.timestamp),
            "msb_serial_number": message.sender,
            "topic": "att",
            "quat1": message.orientation[0],
            "quat2": message.orientation[1],
            "quat3": message.orientation[2],
            "quat4": message.orientation[3],
            "posx": message.position[0],
            "posy": message.position[1],
            "posz": message.position[2],
        }
        socket.send_multipart(
            [
                "lor".encode("utf-8"),
                pickle.dumps(data_dict),
            ]
        )
        time.sleep(0.3)
