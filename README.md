## Kueue
![Build](https://github.com/jarojasm95/kueue/workflows/Build/badge.svg)

Python Distributed Task Queue - backed by Kafka


## Motivation
Kueue was born out of the lack of a library that leverages [Kafka](https://kafka.apache.org/) for distributed task processing

## Features
- simple
- intuitive api

## Code Example
```python
import time
from kueue import task

@task(topic="my-topic")
def sleepy_task(sleep: int):
    time.sleep(sleep)
    return sleep

sleepy_task.enqueue(args=(60))
```

## Installation
```
pip install kueue
```

## Development

Install [poetry](https://python-poetry.org/) and run `poetry install` at the root of the repository. This should create a virtual environment with all the necessary python dependencies.

## Tests
The test framework makes heavy use of `pytest` fixtures in order to spin up full integration environment consisting of a kubernetes cluster using [kind](https://kind.sigs.k8s.io/) and [pytest-kind](https://codeberg.org/hjacobs/pytest-kind) and kafka using [strimzi](https://strimzi.io/)

`pytest`

## License

MIT © [Jose Rojas](https://github.com/jarojasm95)
