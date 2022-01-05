import pickle
import pprint
from collections import deque
from datetime import datetime
from socket import gethostname
import sys
import threading
import time
import zmq

import numpy as np

import logging.config

from driver import LoRaHatDriver
from loraconfig import lora_hat_config, logging_config_dict
from message import Topic, TimeOrientPosMessage

logging.config.dictConfig(logging_config_dict)

socket_name = "tcp://127.0.0.1:5556"
seconds_between_messages = 1

# thread safe, according to:
# https://docs.python.org/3/library/collections.html#collections.deque
buffer = deque(maxlen=1)


def read_from_zeromq(socket_name):
    global buffer
    logging.debug(f"trying to bind zmq to {socket_name}")
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    try:
        with socket.connect(socket_name) as connected_socket:
            # subscribe to all available data
            socket.setsockopt(zmq.SUBSCRIBE, b"")
            logging.debug("successfully bound to zeroMQ receiver socket as subscriber")

            while True:
                topic_bin, data_bin = socket.recv_multipart()
                buffer.append((topic_bin, data_bin))

    except Exception as e:
        logging.critical(f"failed to bind to zeromq socket: {e}")
        sys.exit(-1)


threading.Thread(target=read_from_zeromq, daemon=True, args=[socket_name]).start()

with LoRaHatDriver(lora_hat_config) as lora_hat:
    logging.debug(f"LoRa hat config: {pprint.pformat(lora_hat.config)}")
    sender = int(gethostname()[4:8])
    while True:
        try:
            topic_bin, data_bin = buffer.pop()

            topic = topic_bin.decode("utf-8")
            # data = pickle.loads(data_bin)

            # for debugging: create my own data for now
            data = np.empty(8, dtype=TimeOrientPosMessage.array_dtype)
            data[0] = datetime.utcnow().timestamp()
            data[1:] = np.random.standard_normal(7)

            if topic == "imu":
                message = TimeOrientPosMessage(data, sender, topic=Topic.IMU)
            elif topic == "attitude":
                message = TimeOrientPosMessage(data, sender, topic=Topic.ATTITUDE)
            else:
                message = TimeOrientPosMessage(data, sender)
            lora_hat.send(message.serialize())
        except IndexError:
            logging.debug("No new data to send")
        time.sleep(seconds_between_messages)
