from typing import Callable, Dict, Optional, Union

from confluent_kafka import KafkaError, Message

KafkaHeaders = Dict[str, Optional[Union[str, bytes]]]
ProducerOnDelivery = Callable[[KafkaError, Message], None]
