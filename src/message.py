import pickle
import sys

from abc import ABC, abstractmethod
from enum import Enum, auto

import numpy as np


class Topic(Enum):
    UNDEFINED = auto()
    IMU = auto()
    ATTITUDE = auto()


# https://docs.python-guide.org/scenarios/serialization/


class DeserializeError(ValueError):
    """Raised if a message could not be parsed."""

    pass


class Message(ABC):

    topic = Topic.UNDEFINED
    _sender_dtype = np.ushort

    def __init__(self, content, sender: int, topic: Topic = Topic.UNDEFINED):
        self.content = self._check_content(content)
        self.sender = sender
        self.topic = topic

    @classmethod
    @abstractmethod
    def _check_content(cls, content):
        pass

    @abstractmethod
    def _serialize(self):
        pass

    @classmethod
    @abstractmethod
    def _deserialize(cls, bytes_: bytes):
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.content}, {self.sender}, {str(self.topic)})"

    def __str__(self):
        return f"{self.topic}, from {self.sender}: {self.content}"

    def serialize(self):
        return (
            bytes([self.topic.value])
            + np.array(self.sender, dtype=self._sender_dtype).tobytes()
            + self._serialize()
        )

    @classmethod
    def from_bytes(cls, bytes_: bytes):
        topic = Topic(bytes_[0])
        n_bytes_sender = np.dtype(cls._sender_dtype).itemsize
        sender = np.frombuffer(bytes_[1 : 1 + n_bytes_sender], dtype=cls._sender_dtype)[
            0
        ]
        try:
            data = cls._deserialize(bytes_[1 + n_bytes_sender :])
        except Exception as e:
            raise DeserializeError() from e
        return cls(data, sender, topic)


class TextMessage(Message):
    def __repr__(self):
        return f'{self.__class__.__name__}("{self.content}", {self.sender}, {str(self.topic)})'

    def _serialize(self):
        return self.content.encode("utf-8")

    @classmethod
    def _check_content(cls, content):
        if type(content) != str:
            raise TypeError(
                f"{cls.__name__} expects a str content but got {type(content)}."
            )
        return content

    @classmethod
    def _deserialize(cls, bytes_: bytes):
        return bytes_.decode("utf-8")


class PickleMessage(Message):
    def _serialize(self):
        return pickle.dumps(self.content)

    @classmethod
    def _check_content(cls, content):
        return content

    @classmethod
    def _deserialize(cls, bytes_: bytes):
        return pickle.loads(bytes_)


class NumpyMessage(Message):

    array_dtype = np.float32

    @classmethod
    def _check_content(cls, content):
        if type(content) != np.ndarray:
            raise TypeError(
                f"{cls.__name__} expects a numpy array content but got {type(content)}."
            )
        if content.shape != (len(content),):
            raise ValueError("array must be flat.")
        if content.dtype != cls.array_dtype:
            raise ValueError(f"array must be of type {cls.array_dtype}.")
        return content

    def _serialize(self):
        return self.content.tobytes()

    @classmethod
    def _deserialize(cls, bytes_: bytes):
        return np.frombuffer(bytes_, dtype=cls.array_dtype)


class TimeOrientPosMessage(NumpyMessage):
    @classmethod
    def _check_content(cls, content):
        content = super()._check_content(content)
        if len(content) != 8:
            raise ValueError(
                f"{cls.__name__} expects an 8 element array as content but got len {len(content)}."
            )
        return content

    @property
    def timestamp(self):
        return self.content[0]

    @property
    def orientation(self):
        return self.content[1:5]

    @property
    def position(self):
        return self.content[5:8]
