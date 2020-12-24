from unittest.mock import MagicMock, Mock

from confluent_kafka import KafkaError, KafkaException
from pytest_mock import MockerFixture

from kueue import KueueConfig, TaskExecutorConsumer


def test_consumer_stop(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    mocker.patch.object(consumer, "_kafka")
    mock_consume: MagicMock = mocker.patch.object(consumer, "consume", return_value=["test"])
    on_exit = mocker.spy(consumer, "on_exit")

    for idx, message in enumerate(consumer):
        assert message == "test"
        assert idx == 0
        consumer.stop()

    mock_consume.assert_called_once()
    on_exit.assert_called_once()


def test_consumer_consume_success(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    message = Mock(error=Mock(return_value=None))
    kafka = mocker.patch.object(consumer, "_kafka")
    kafka.consume.return_value = [message]

    result = consumer.consume()

    assert result == [message]
    kafka.consume.assert_called_once_with(
        num_messages=dummy_config.consume_defaults.prefetch,
        timeout=dummy_config.consume_defaults.timeout,
    )


def test_consumer_consume_kafka_exception(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    kafka = mocker.patch.object(consumer, "_kafka")
    kafka.consume.side_effect = KafkaException(KafkaError(KafkaError.UNKNOWN))
    on_consume_error = mocker.spy(consumer, "on_consume_error")

    result = consumer.consume()

    assert result == []
    on_consume_error.assert_called_once()
    kafka.consume.assert_called_once_with(
        num_messages=dummy_config.consume_defaults.prefetch,
        timeout=dummy_config.consume_defaults.timeout,
    )


def test_consumer_consume_timeout(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    kafka = mocker.patch.object(consumer, "_kafka")
    kafka.consume.return_value = []
    on_timeout = mocker.spy(consumer, "on_timeout")

    result = consumer.consume()

    assert result == []
    on_timeout.assert_called_once()
    kafka.consume.assert_called_once_with(
        num_messages=dummy_config.consume_defaults.prefetch,
        timeout=dummy_config.consume_defaults.timeout,
    )


def test_consumer_consume_message_error(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    message = Mock(error=Mock(return_value=Mock(code=Mock(return_value="error!"))))
    kafka = mocker.patch.object(consumer, "_kafka")
    kafka.consume.return_value = [message]
    on_consume_error = mocker.spy(consumer, "on_consume_error")

    result = consumer.consume()

    assert result == []
    on_consume_error.assert_called_once()
    kafka.consume.assert_called_once_with(
        num_messages=dummy_config.consume_defaults.prefetch,
        timeout=dummy_config.consume_defaults.timeout,
    )


def test_consumer_consume_eof(dummy_config: KueueConfig, mocker: MockerFixture):
    consumer = TaskExecutorConsumer(["dummy"])
    message = Mock(error=Mock(return_value=Mock(code=Mock(return_value=KafkaError._PARTITION_EOF))))
    kafka = mocker.patch.object(consumer, "_kafka")
    kafka.consume.return_value = [message]
    on_eof = mocker.spy(consumer, "on_eof")

    result = consumer.consume()

    assert result == []
    on_eof.assert_called_once()
    kafka.consume.assert_called_once_with(
        num_messages=dummy_config.consume_defaults.prefetch,
        timeout=dummy_config.consume_defaults.timeout,
    )
