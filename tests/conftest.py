from pathlib import Path

import pytest

from kueue.config import KueueConfig
from kueue.task import TaskExecution
from tests.utils.helm import Helm
from tests.utils.kind import KindCluster
from tests.utils.tasks import return_args


@pytest.fixture(scope="session")
def helm(kind_cluster: KindCluster) -> Helm:
    helm = Helm(kubeconfig=kind_cluster.kubeconfig_path)
    helm.ensure_helm()
    return helm


@pytest.fixture(scope="session")
def kafka(helm: Helm, kind_cluster: KindCluster, request) -> KueueConfig:
    keep = request.config.getoption("keep_cluster")
    skip_helm = request.config.getoption("skip_helm")
    if not skip_helm:
        # TODO: wait for kafka
        helm.install("kueue", "kueue", upgrade=True)
    kind_cluster.ensure_kubectl()
    # TODO: Patch kafka services to run at this port, then restart kafka and wait until ready
    # TODO: Use hostsman to add kind node
    yield "localhost:30092"
    if not keep and not skip_helm:
        helm.uninstall("kueue")


@pytest.fixture(scope="session")
def kueue_config(kafka: str) -> KueueConfig:
    yield KueueConfig(kafka=kafka)


@pytest.fixture(scope="session")
def kind_cluster(request) -> KindCluster:
    """Provide a Kubernetes kind cluster as test fixture"""
    name = request.config.getoption("cluster_name")
    keep = request.config.getoption("keep_cluster")
    kubeconfig = request.config.getoption("kubeconfig")
    cluster = KindCluster(name, Path(kubeconfig) if kubeconfig else None)
    cluster.create("kind.yaml")
    yield cluster
    if not keep:
        cluster.delete()


def kueue_task_execution() -> TaskExecution:
    return TaskExecution.parse_obj({"name": return_args, "args": [1], "kwargs": {"test": True}})


def pytest_addoption(parser, pluginmanager):
    group = parser.getgroup("kueue")
    group.addoption("--skip-helm", dest="skip_helm", action="store_true", default=False)
