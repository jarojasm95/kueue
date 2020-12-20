import functools
from typing import Set

from pydantic import BaseModel, PositiveInt, PyObject

from kueue._types import KafkaHeaders, ProducerOnDelivery


def pydantic_singleton(clazz):
    class wrapper(clazz):

        _instance = None
        _initialized = False

        @functools.wraps(clazz.__new__)
        def __new__(cls, *args, **kwargs):
            # Only call the real constructor once.
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

        @functools.wraps(clazz.__init__)
        def __init__(self, *args, **kwargs):
            # Only initialize the instance once.
            if not self.__class__._initialized:
                super().__init__(*args, **kwargs)
            self.__class__._initialized = True

        @classmethod
        def singleton_reset_(cls):
            cls._instance = None
            cls._initialized = False

    wrapper.__module__ = clazz.__module__
    wrapper.__name__ = clazz.__name__
    if hasattr(clazz, "__qualname__"):
        wrapper.__qualname__ = clazz.__qualname__

    return wrapper


class ProducerDefaults(BaseModel):
    """
    Default arguments to use when calling Producer().produce()
    """

    key: str = None
    headers: KafkaHeaders = None
    on_delivery: ProducerOnDelivery = None
    partition: int = None


class ConsumeDefaults(BaseModel):
    """
    Default arguments to use when calling Consumer().consume()
    """

    timeout: int = 5  # seconds
    prefetch: PositiveInt = 1


@pydantic_singleton
class KueueConfig(BaseModel):
    """
    Main config class for Kueue
    """

    kafka_bootstrap: str  # Kafka bootstrap service

    topics: Set = set()  # Topics used / allowed
    default_topic: str = None  # Default topic to use

    # librdkafka config for consumer/producer
    # https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md
    consumer_config: dict = {}
    producer_config: dict = {}

    produce_defaults: ProducerDefaults = ProducerDefaults()
    consume_defaults: ConsumeDefaults = ConsumeDefaults()

    task_executor: PyObject = None
    task_config_cls: PyObject = None
