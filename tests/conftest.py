import logging
import uuid
from contextlib import suppress
from pathlib import Path
from subprocess import CalledProcessError
from typing import Tuple

import pytest
import yaml
from hostsman import Host

from kueue import KueueConfig
from tests.utils.helm import Helm
from tests.utils.kind import KindCluster


@pytest.fixture
def logger(request) -> logging.Logger:
    return logging.getLogger(request.node.name)


@pytest.fixture(scope="session")
def helm(kind_cluster: KindCluster) -> Helm:
    helm = Helm(kubeconfig=kind_cluster.kubeconfig_path)
    helm.ensure_helm()
    return helm


@pytest.fixture(scope="session")
def kafka_ports(request) -> Tuple[int, int]:
    with request.config.getoption("kind_config").open() as config:
        kind_config = yaml.safe_load(config)
    return (
        kind_config["nodes"][0]["extraPortMappings"][-2]["hostPort"],
        kind_config["nodes"][0]["extraPortMappings"][-1]["hostPort"],
    )


@pytest.fixture
def topic_name(request):
    suffix = uuid.uuid4().hex[:5]
    return f"{request.node.name}-{suffix}"


@pytest.fixture(scope="session")
def kafka_bootstrap(
    helm: Helm, kind_cluster: KindCluster, kafka_ports: Tuple[int, int], request
) -> KueueConfig:
    kafka_bootstrap = request.config.getoption("kafka_bootstrap")
    if kafka_bootstrap:
        yield kafka_bootstrap
        return

    need_install = True
    with suppress(CalledProcessError):
        result, err = helm.status("kueue")
        if result["info"]["status"] == "deployed":
            need_install = False
    if need_install:
        helm.install("kueue", "kueue", upgrade=True)

    kind_cluster.wait_for_pod("kueue-kafka-0")
    restart_needed = False
    bootstrap_port, broker_port = kafka_ports
    with kind_cluster.service_update("kueue-kafka-external-bootstrap") as bootstrap:
        if bootstrap.obj["spec"]["ports"][0]["nodePort"] != bootstrap_port:
            restart_needed = True
            bootstrap.obj["spec"]["ports"][0]["nodePort"] = bootstrap_port
    with kind_cluster.service_update("kueue-kafka-0") as bootstrap:
        if bootstrap.obj["spec"]["ports"][0]["nodePort"] != broker_port:
            restart_needed = True
            bootstrap.obj["spec"]["ports"][0]["nodePort"] = broker_port
    if restart_needed:
        kind_cluster.delete_pod("kueue-kafka-0")
        kind_cluster.wait_for_pod("kueue-kafka-0")
    if not Host().exists("kueue-control-plane"):
        Host(keepingHistory=False).add("kueue-control-plane")
    yield f"kueue-control-plane:{bootstrap_port}"
    if not request.config.getoption("keep_cluster"):
        helm.uninstall("kueue")


@pytest.fixture()
def kueue_config(kafka_bootstrap: str) -> KueueConfig:
    yield KueueConfig(kafka_bootstrap=kafka_bootstrap)
    KueueConfig().singleton_reset_()


@pytest.fixture()
def dummy_config() -> KueueConfig:
    yield KueueConfig(kafka_bootstrap="localhost:9092")
    KueueConfig().singleton_reset_()


@pytest.fixture(scope="session")
def kind_cluster(request) -> KindCluster:
    """Provide a Kubernetes kind cluster as test fixture"""
    keep = request.config.getoption("keep_cluster")
    kubeconfig = request.config.getoption("kubeconfig")
    cluster = KindCluster("kueue", Path(kubeconfig) if kubeconfig else None)
    cluster.create(request.config.getoption("kind_config"))
    cluster.kubeconfig_path.chmod(0o600)
    cluster.ensure_kubectl()
    yield cluster
    if not keep:
        cluster.delete()


def pytest_addoption(parser, pluginmanager):
    group = parser.getgroup("kueue")
    group.addoption(
        "--kind-config",
        dest="kind_config",
        action="store",
        type=Path,
        default=Path("kind.yaml"),
        help="Path to kind cluster config",
    )
    group.addoption(
        "--kafka-bootstrap",
        dest="kafka_bootstrap",
        action="store",
        help="location of kafka bootstrap service for integration tests",
        default=None,
    )
    group.addoption("--integration", action="store_true", help="run integration tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--integration"):
        # --integration given in cli: do not skip slow tests
        return
    skip_integration = pytest.mark.skip(reason="need --integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
