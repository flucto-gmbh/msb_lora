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
from config_lora import lora_hat_config, logging_config_dict
from message import Topic, TimeAttGPSMessage

logging.config.dictConfig(logging_config_dict)

# overwrite msb specifics in lora hat config
try:
    import config_msb

    lora_hat_config.update(config_msb.lora_hat_config)
except ImportError:
    pass


socket_name = "tcp://127.0.0.1:5556"
seconds_between_messages = 1

# thread safe, according to:
# https://docs.python.org/3/library/collections.html#collections.deque
orient_buffer = deque(maxlen=1)
pos_buffer = deque(maxlen=1)

ATTITUDE_TOPIC = "att".encode("utf-8")
GPS_TOPIC = "gps".encode("utf-8")


def read_from_zeromq(socket_name):
    global orient_buffer
    global pos_buffer
    logging.debug(f"trying to bind zmq to {socket_name}")
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    try:
        with socket.connect(socket_name) as connected_socket:
            # subscribe to att and gps
            socket.setsockopt(zmq.SUBSCRIBE, ATTITUDE_TOPIC)
            socket.setsockopt(zmq.SUBSCRIBE, GPS_TOPIC)
            logging.debug("successfully bound to zeroMQ receiver socket as subscriber")

            while True:
                topic_bin, data_bin = socket.recv_multipart()
                if topic_bin == ATTITUDE_TOPIC:
                    orient_buffer.append(data_bin)
                elif topic_bin == GPS_TOPIC:
                    pos_buffer.append(data_bin)
                else:
                    assert False

    except Exception as e:
        logging.critical(f"failed to bind to zeromq socket: {e}")
        sys.exit(-1)


threading.Thread(target=read_from_zeromq, daemon=True, args=[socket_name]).start()

with LoRaHatDriver(lora_hat_config) as lora_hat:
    logging.debug(f"LoRa hat config: {pprint.pformat(lora_hat.config)}")
    sender = int(gethostname()[4:8])
    while True:
        try:
            orient_data_bin = orient_buffer.pop()
            pos_data_bin = orient_buffer.pop()

            orient_data = pickle.loads(orient_data_bin)
            pos_data = pickle.loads(pos_data_bin)

            assert len(orient_data) == 5

            data = {
                "timestamp": np.array(
                    orient_data[0], dtype=TimeAttGPSMessage.timestamp_dtype
                ),
                "attitude": np.array(
                    orient_data[1:5], dtype=TimeAttGPSMessage.attitude_dtype
                ),
                "gps": np.array(
                    [pos_data["lat"], pos_data["lon"], pos_data["alt"]],
                    dtype=TimeAttGPSMessage.gps_dtype,
                ),
            }

            # for debugging: create my own data for now
            # data = np.empty(8, dtype=TimeOrientPosMessage.array_dtype)
            # data[0] = datetime.utcnow().timestamp()
            # data[1:] = np.random.standard_normal(7)

            message = TimeAttGPSMessage(data, sender, topic=Topic.ATTITUDE_AND_GPS)

            lora_hat.send(message.serialize())
        except IndexError:
            logging.debug("No new data to send")
        time.sleep(seconds_between_messages)
