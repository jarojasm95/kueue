from types import FunctionType, MethodType
from typing import Type

from confluent_kafka import Producer
from pydantic import BaseModel, Field, PyObject, validator
from pydantic.main import ModelMetaclass
from wrapt import FunctionWrapper

from kueue._types import KafkaHeaders, ProducerOnDelivery
from kueue.config import KueueConfig

DEFAULT_JSON_ENCODERS = {
    FunctionType: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
    MethodType: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
    Type: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
    ModelMetaclass: lambda v: "{}.{}".format(v.__module__, v.__qualname__),
}


def dict_if_not_none(**kwargs):
    return {k: v for (k, v) in kwargs.items() if v is not None}


class TaskExecutor(BaseModel):
    """
    Task execution class, encapsulates a task and the parameters used to run it
    """

    class Config:
        json_encoders = DEFAULT_JSON_ENCODERS

    task: PyObject
    args: tuple
    kwargs: dict
    executor: str = None

    @validator("executor", pre=True, always=True)
    def executor_serialize(cls, v):
        if isinstance(v, str):
            return v
        if v is None:
            v = cls
        serializer = cls.Config.json_encoders.get(type(v))
        return serializer(v)

    @property
    def task_name(self):
        return f"{self.task.__module__}.{self.task.__qualname__}"

    def run(self):
        return self.task(*self.args, **self.kwargs)


class TaskProducer(Producer):
    def __init__(self, **config):
        super().__init__(
            {
                "bootstrap.servers": KueueConfig().kafka_bootstrap,
                **KueueConfig().producer_config,
                **config,
            }
        )


class TaskConfig(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    topic: str = Field(default_factory=lambda: KueueConfig().default_topic)
    key: str = Field(default_factory=lambda: KueueConfig().produce_defaults.key)
    producer: TaskProducer = Field(default_factory=TaskProducer)

    headers: KafkaHeaders = Field(default_factory=lambda: KueueConfig().produce_defaults.headers)
    partition: int = Field(default_factory=lambda: KueueConfig().produce_defaults.partition)
    on_delivery: ProducerOnDelivery = Field(
        default_factory=lambda: KueueConfig().produce_defaults.on_delivery
    )

    @validator("topic", always=True)
    def valid_topic(cls, v):
        if not v:
            raise ValueError(f"Invalid task topic: {v}")
        if KueueConfig().topics and v not in KueueConfig().topics:
            raise ValueError(f"Invalid task topic: {v}")
        return v

    def produce(
        self,
        executor: TaskExecutor,
        *,
        key: str = None,
        partition: int = None,
        on_delivery: ProducerOnDelivery = None,
        timestamp: int = None,
        headers: KafkaHeaders = None,
    ):
        kwargs = dict(  # noqa: C408
            key=key or executor.task_name,
            partition=partition or self.partition,
            on_delivery=on_delivery or self.on_delivery,
            timestamp=timestamp,
            headers=headers or self.headers,
        )
        return self.producer.produce(
            self.topic,
            executor.json(),
            **{k: v for (k, v) in kwargs.items() if v is not None},
        )


class TaskProxy(FunctionWrapper):
    def __init__(
        self,
        wrapped,
        *,
        task_config_cls: Type[TaskConfig],
        task_executor: Type[TaskExecutor],
        **kwargs,
    ):
        super(TaskProxy, self).__init__(wrapped, wrapped, enabled=False)
        task_config_cls = task_config_cls or KueueConfig().task_config_cls or TaskConfig
        task_executor = task_executor or KueueConfig().task_executor or TaskExecutor
        self.task_config: TaskConfig = task_config_cls(**kwargs)
        self.task_executor: Type[TaskExecutor] = task_executor

    @property
    def name(self):
        return f"{self.__wrapped__.__module__}.{self.__wrapped__.__qualname__}"

    def enqueue(
        self, *, args: tuple = (), kwargs: dict = {}, task_extra: dict = {}, **producer_options
    ):
        return self.task_config.produce(
            self.task_executor(
                task=self.__wrapped__,
                args=args,
                kwargs=kwargs,
                **task_extra,
            ),
            **producer_options,
        )

    def __repr__(self):
        return f"<@task: {self.name}>"

    __str__ = __repr__


def task(
    func=None,
    task_config_cls: Type[TaskConfig] = None,
    task_executor: Type[TaskExecutor] = None,
    **task_config,
):
    def _wrapper(func):
        return TaskProxy(
            func, task_config_cls=task_config_cls, task_executor=task_executor, **task_config
        )

    if func is None:
        return _wrapper
    return _wrapper(func)
