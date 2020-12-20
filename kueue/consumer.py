import logging
import signal
import socket
from contextlib import contextmanager, suppress
from enum import Enum
from typing import List, Optional

from confluent_kafka import (
    TIMESTAMP_CREATE_TIME,
    TIMESTAMP_LOG_APPEND_TIME,
    TIMESTAMP_NOT_AVAILABLE,
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    ThrottleEvent,
    TopicPartition,
)
from pydantic import BaseModel, Json, PyObject, validator

from kueue.config import KueueConfig
from kueue.task import TaskExecutor


class TimestampType(Enum):

    NotAvailable = TIMESTAMP_NOT_AVAILABLE
    Broker = TIMESTAMP_LOG_APPEND_TIME
    Producer = TIMESTAMP_CREATE_TIME


class TaskMessage(BaseModel):

    topic: str
    partition: int
    offset: int
    key: Optional[str] = None
    value: Json
    timestamp_type: TimestampType
    timestamp: Optional[int]

    @validator("timestamp")
    def timestamp_to_seconds(cls, v, values):
        if values.get("timestamp_type") == TimestampType.NotAvailable:
            return None
        return v / 1000.0

    def executor(self) -> TaskExecutor:
        return PyObject.validate(self.value["executor"]).parse_obj(self.value)

    @classmethod
    def parse_kafka_message(cls, message: Message) -> "TaskMessage":
        ts_type, ts = message.timestamp()
        return cls(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=message.key(),
            value=message.value(),
            timestamp=ts,
            timestamp_type=ts_type,
            size=len(message),
        )


class ConsumerBase:
    def __init__(self, **config):
        name = f"{self.__class__.__module__}.{self.__class__.__qualname__}"
        self.logger = logging.getLogger(name)
        self.consumer = Consumer(
            {
                "bootstrap.servers": KueueConfig().kafka_bootstrap,
                "group.id": name,
                "client.rack": socket.gethostname(),
                "enable.auto.commit": False,
                "on_commit": self.on_commit,
                "error_cb": self.on_internal_error,
                "throttle_cb": self.on_throttle,
                "auto.offset.reset": "earliest",
                "api.version.request": True,
                **KueueConfig().consumer_config,
                **config,
            }
        )
        self._exit = False
        self._setup_signal_handling()

    def on_assign(self, _, partitions: List[TopicPartition]):
        self.logger.info("on_assign: %s", partitions)

    def on_revoke(self, _, partitions: List[TopicPartition]):
        self.logger.info("on_revoke: %s", partitions)

    def on_exit(self):
        self.logger.info("on_exit")

    def on_throttle(self, event: ThrottleEvent):
        self.logger.warning("on_throttle")

    def on_stats(self, stats: str):
        self.logger.info("on_stats: %s", stats)

    def on_commit(self, error: Optional[KafkaError], partitions: List[TopicPartition]):
        self.logger.info("on_commit: %s | %s", error, partitions)

    def on_timeout(self):
        self.logger.warning("on_timeout")

    def on_internal_error(self, error: KafkaError, message: Message = None):
        self.logger.exception("on_internal_error: %s | %s", error, message)

    def on_eof(self):
        self.logger.warning("on_eof")

    def consume(self) -> List[Message]:
        try:
            messages: List[Message] = self.consumer.consume(
                num_messages=KueueConfig().consume_defaults.prefetch,
                timeout=KueueConfig().consume_defaults.timeout,
            )
        except KafkaError as e:
            self.on_internal_error(e)
            return []
        except KafkaException as e:
            self.on_internal_error(e.args[0])
            return []
        if not messages:
            self.on_timeout()
            return []
        errors = filter(lambda msg: msg.error(), messages)
        messages = filter(lambda msg: not msg.error(), messages)
        for error_msg in errors:
            if error_msg.error().code() == KafkaError._PARTITION_EOF:
                self.on_eof(error_msg)
            else:
                self.on_internal_error(error_msg.error(), error_msg)
        return messages

    def _iterator(self):
        while not self._exit:
            messages = self.consume()
            for message in messages:
                yield message

    def _setup_signal_handling(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signal=None, frame=None):
        self._exit = True
        self.on_exit()

    @contextmanager
    def stream(self):
        try:
            yield self._iterator()
        finally:
            self.consumer.close()


class TaskExecutorConsumer(ConsumerBase):
    """
    Consumer class for task execution
    """

    def __init__(self, topics: List[str], **config):
        super().__init__(**config)
        self.consumer.subscribe(topics, on_assign=self.on_assign, on_revoke=self.on_revoke)

    def on_message(self, message: TaskMessage):
        return message.executor().run()

    def on_success(self, message: TaskMessage, result):
        self.logger.info("on_success: %s | %s", message, result)

    def on_error(self, message: TaskMessage):
        self.logger.exception("on_error: %s | %s", message)

    def on_commit(self, error: Optional[KafkaError], partitions: List[TopicPartition]):
        self.logger.info("on_commit: %s | %s", error, partitions)

    def dispatch_message(self, message: Message):
        parsed = TaskMessage.parse_kafka_message(message)
        try:
            result = self.on_message(parsed)
        except Exception:
            with suppress(Exception):
                self.on_error(parsed)
        else:
            with suppress(Exception):
                self.on_success(parsed, result)

        try:
            commits: List[TopicPartition] = self.consumer.commit(
                message=message, asynchronous=False
            )
        except KafkaException as e:
            self.on_commit(e.args[0], [])
        else:
            self.on_commit(None, commits)

    def start(self):
        """
        Start message consumption
        Should be used when the consumer is defined as a subclass of `Consumer`
        or if callbacks are configured using the `*_handler` decorators
        """
        with self.stream() as message_stream:
            for message in message_stream:
                self.dispatch_message(message)
