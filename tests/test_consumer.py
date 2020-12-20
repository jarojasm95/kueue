import uuid
from concurrent.futures import Future

import pytest
from confluent_kafka import Message
from pytest_mock import MockerFixture

from kueue import KueueConfig, task
from kueue.task import TaskExecutor, TaskProducer
from tests.utils.tasks import SingleTaskConsumer, return_args


@pytest.mark.integration
def test_task_execution(kueue_config: KueueConfig, mocker: MockerFixture, topic_name: str):
    task_request = TaskExecutor(task=return_args, args=[uuid.uuid4().hex], kwargs={"test": True})
    producer = TaskProducer()

    message = Future()
    producer.produce(
        topic_name, task_request.json(), on_delivery=lambda err, msg: message.set_result(msg)
    )
    producer.flush(timeout=5)
    message: Message = message.result(timeout=5)

    mock = mocker.patch("tests.utils.tasks.return_args")
    execution = SingleTaskConsumer([topic_name])
    execution.start()
    mock.assert_called_once_with(*task_request.args, **task_request.kwargs)


@pytest.mark.integration
def test_task_enqueue(kueue_config: KueueConfig, mocker: MockerFixture, topic_name: str):
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
