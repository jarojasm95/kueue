FROM python:3.8.6-buster as installer

RUN apt-get update && \
    apt-get -y --no-install-recommends install \
    gettext \
    gcc \
    g++ \
    curl

ARG POETRY_VERSION=1.1.4
ENV PATH /root/.poetry/bin:$PATH
RUN pip install --upgrade pip && \
    curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
ENV POETRY_VIRTUALENVS_CREATE="false"
ENV POETRY_INSTALLER_PARALLEL="false"
WORKDIR /home/kueue

ENV PATH /home/kueue/.venv/bin:$PATH

RUN python -m venv /home/kueue/.venv && \
    pip install --upgrade pip

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root

FROM python:3.8.6-slim-buster

WORKDIR /home/kueue

RUN useradd -m -U -d /home/kueue kueue

COPY --from=installer --chown=kueue:kueue /home/kueue/.venv /home/kueue/.venv
ENV PATH /home/kueue/.venv/bin:$PATH

RUN chown -R kueue:kueue /home/kueue
USER kueue

COPY pyproject.toml ./
COPY kueue kueue
COPY tests tests
