from types import FunctionType, MethodType
from typing import Optional

from confluent_kafka import Consumer, KafkaException, Message, TopicPartition
from pydantic import BaseModel, PyObject

from kueue.config import KueueConfig


class TaskExecutionConsumer(Consumer):
    def __init__(self, topic: str, partition: int, offset: int, config: KueueConfig = None):
        config = config or KueueConfig()
        super().__init__(
            {
                "bootstrap.servers": config.kafka,
                "group.id": f"{topic}-{partition}-{offset}",
                "enable.auto.commit": False,
            }
        )
        self.assign([TopicPartition(topic, partition, offset)])

    def subscribe(self, *args, **kwargs):
        raise RuntimeError("TaskExecutionConsumer does not support 'subscribe()'")

    def commit(self, *args, **kwargs):
        raise RuntimeError("TaskExecutionConsumer does not support 'commit()'")

    def run(self):
        msg: Message = self.consume()[0]
        if msg is None:
            raise ValueError
        if msg.error():
            raise KafkaException(msg.error())
        task_msg = TaskMessage.from_kafka_message(msg)
        return task_msg.task.name(*task_msg.task.args, **task_msg.task.kwargs)


class TaskExecution(BaseModel):
    class Config:
        json_encoders = {
            FunctionType: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
            MethodType: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
        }

    name: PyObject
    args: tuple
    kwargs: dict


class TaskMessage(BaseModel):

    topic: str
    partition: int
    offset: int
    key: Optional[int] = None

    task: TaskExecution

    @classmethod
    def from_kafka_message(cls, message: Message) -> "TaskMessage":
        return cls.parse_obj(
            {
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
                "key": message.key(),
                "task": TaskExecution.parse_raw(message.value()),
            }
        )
