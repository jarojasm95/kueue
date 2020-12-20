import json
import logging
import uuid
from concurrent.futures import Future

import pytest
from confluent_kafka import Message, TopicPartition
from pytest_mock import MockerFixture

from kueue import KueueConfig, task
from kueue.consumer import ConsumerBase, TaskMessage
from kueue.task import TaskProducer
from tests.utils.tasks import SingleTaskConsumer, return_args


@pytest.mark.integration
def test_task_consumption(
    kueue_config: KueueConfig, mocker: MockerFixture, topic_name: str, logger: logging.Logger
):
    producer = TaskProducer()
    args = (uuid.uuid4().hex,)
    kwargs = {"test": True}

    message = Future()
    producer.produce(
        topic_name,
        json.dumps(
            {
                "task": "tests.utils.tasks.return_args",
                "args": list(args),
                "kwargs": kwargs,
                "executor": "kueue.task.TaskExecutor",
            }
        ),
        on_delivery=lambda err, msg: message.set_result(msg),
    )
    logger.info("produced, flushing")
    producer.flush(timeout=5)
    logger.info("flushed, waiting")
    message: Message = message.result(timeout=5)

    mock = mocker.patch("tests.utils.tasks.return_args")
    logger.info("starting consumer")
    execution = SingleTaskConsumer([topic_name])
    execution.start()
    mock.assert_called_once_with(*args, **kwargs)


@pytest.mark.integration
def test_task_produce(kueue_config: KueueConfig, mocker: MockerFixture, topic_name: str):
    tasked = task(topic=topic_name)(return_args)
    args = (uuid.uuid4().hex,)
    kwargs = {"test": True}
    message = Future()
    tasked.enqueue(args=args, kwargs=kwargs, on_delivery=lambda err, msg: message.set_result(msg))
    tasked.task_config.producer.flush(timeout=5)
    message: Message = message.result(timeout=5)

    consumer = ConsumerBase()
    consumer.kafka.assign([TopicPartition(message.topic(), message.partition(), message.offset())])
    messages = consumer.consume()
    consumer.kafka.close()
    assert len(messages) == 1

    task_message = TaskMessage.parse_kafka_message(messages[0])
    assert task_message.value["task"] == "tests.utils.tasks.return_args"
    assert task_message.value["args"] == list(args)
    assert task_message.value["kwargs"] == kwargs


@pytest.mark.integration
def test_end_to_end(kueue_config: KueueConfig, mocker: MockerFixture, topic_name: str):
    tasked = task(topic=topic_name)(return_args)
    args = (uuid.uuid4().hex,)
    kwargs = {"test": True}
    message = Future()
    tasked.enqueue(args=args, kwargs=kwargs, on_delivery=lambda err, msg: message.set_result(msg))
    tasked.task_config.producer.flush(timeout=5)
    message: Message = message.result(timeout=5)

    mock = mocker.patch("tests.utils.tasks.return_args")
    execution = SingleTaskConsumer([topic_name])
    execution.start()
    mock.assert_called_once_with(*args, **kwargs)
