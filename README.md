## Kueue
[![pypi](https://img.shields.io/pypi/v/kueue.svg)](https://pypi.org/project/kueue)
[![pypi](https://img.shields.io/pypi/pyversions/kueue.svg)](https://pypi.org/project/kueue)
[![CI](https://github.com/jarojasm95/kueue/workflows/Build/badge.svg?event=push)](https://github.com/jarojasm95/kueue/actions?query=branch%3Amain+event%3Apush+workflow%3ABuild)
[![style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![license](https://img.shields.io/github/license/jarojasm95/kueue.svg)](https://github.com/jarojasm95/kueue/blob/main/LICENSE)


Python Distributed Task Queue - backed by Kafka


## Motivation
Kueue was born out of the lack of a library that leverages [Kafka](https://kafka.apache.org/) for distributed task processing

## Features
- simple
- intuitive api
- extensible

## Code Example
```python
import time
from kueue import task, TaskExecutorConsumer, KueueConfig

KueueConfig(
    kafka_bootstrap='localhost:9092'
)

@task(topic="my-topic")
def sleepy_task(sleep: int):
    time.sleep(sleep)
    print("done sleeping", sleep)
    return sleep

sleepy_task.enqueue(args=(15,))

consumer = TaskExecutorConsumer(["my-topic"])
consumer.start()
# prints "done sleeping, 15"
```

## Installation
```
pip install kueue
```

## Development

Install [poetry](https://python-poetry.org/) and run `poetry install` at the root of the repository. This should create a virtual environment with all the necessary python dependencies.

## Tests
The test framework makes heavy use of `pytest` fixtures in order to spin up full integration environment consisting of a kubernetes cluster using [kind](https://kind.sigs.k8s.io/) and [pytest-kind](https://codeberg.org/hjacobs/pytest-kind) and kafka using [strimzi](https://strimzi.io/)

```bash
# unit tests
pytest
# unit tests + integration tests
pytest --integration
````

## License

MIT © [Jose Rojas](https://github.com/jarojasm95)
