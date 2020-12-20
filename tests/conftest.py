import uuid
from pathlib import Path
from typing import Tuple

import pytest
from hostsman import Host

from kueue import KueueConfig
from tests.utils.helm import Helm
from tests.utils.kind import KindCluster


@pytest.fixture(scope="session")
def helm(kind_cluster: KindCluster) -> Helm:
    helm = Helm(kubeconfig=kind_cluster.kubeconfig_path)
    helm.ensure_helm()
    return helm


@pytest.fixture(scope="session")
def kafka_ports() -> Tuple[int, int]:
    return 30092, 30094


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
    skip_helm = request.config.getoption("skip_helm")
    if not skip_helm:
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
        Host().add("kueue-control-plane")
    yield f"kueue-control-plane:{bootstrap_port}"
    if not request.config.getoption("keep_cluster") and not skip_helm:
        helm.uninstall("kueue")


@pytest.fixture()
def kueue_config(kafka_bootstrap: str) -> KueueConfig:
    yield KueueConfig(kafka_bootstrap=kafka_bootstrap)
    KueueConfig().singleton_reset_()


@pytest.fixture()
def fast_produce_kueue_config(kafka_bootstrap: str) -> KueueConfig:
    yield KueueConfig(
        kafka_bootstrap=kafka_bootstrap,
        producer_config={
            "request.required.acks": 0,
        },
    )
    KueueConfig().singleton_reset_()


@pytest.fixture(scope="session")
def kind_cluster(request) -> KindCluster:
    """Provide a Kubernetes kind cluster as test fixture"""
    keep = request.config.getoption("keep_cluster")
    kubeconfig = request.config.getoption("kubeconfig")
    cluster = KindCluster("kueue", Path(kubeconfig) if kubeconfig else None)
    cluster.create(request.config.getoption("kind_config"))
    cluster.ensure_kubectl()
    yield cluster
    if not keep:
        cluster.delete()


def pytest_addoption(parser, pluginmanager):
    group = parser.getgroup("kueue")
    group.addoption(
        "--skip-helm",
        dest="skip_helm",
        action="store_true",
        default=False,
        help="skip helm install / uninstall",
    )
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
