from concurrent.futures import Future

from confluent_kafka import Producer

from kueue.config import KueueConfig
from kueue.task import TaskExecution, TaskExecutionConsumer
from tests.utils.tasks import return_args


def test_myapp(kueue_config: KueueConfig):
    task_request = TaskExecution(name=return_args, args=[1], kwargs={"test": True})
    producer = Producer({"bootstrap.servers": kueue_config.kafka})

    message = Future()

    def delivery_report(err, msg):
        message.set_result(msg)

    producer.produce("test", task_request.json(), on_delivery=delivery_report)
    producer.flush()
    while not message.done():
        producer.poll(2)

    message = message.result()

    task = TaskExecutionConsumer(
        message.topic(), message.partition(), message.offset(), config=kueue_config
    )

    assert task.run() == (task_request.args, task_request.kwargs)
