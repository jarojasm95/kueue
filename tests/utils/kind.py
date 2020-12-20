import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pykube import Pod, Service
from pytest_kind import KindCluster as KC


class KindCluster(KC):
    def __init__(self, name: str, kubeconfig: Optional[Path] = None):
        self.name = name
        self.kubeconfig = kubeconfig
        self.path = Path(".venv/bin").absolute()
        self.path.mkdir(parents=True, exist_ok=True)
        self.kind_path = self.path / "kind"
        self.kubectl_path = self.path / "kubectl"

    @contextmanager
    def service_update(self, name: str):
        svc = Service.objects(self.api).get_by_name(name=name)
        yield svc
        svc.update()
        time.sleep(3)

    def wait_for_pod(self, name: str) -> Pod:
        pod = None
        while pod is None or not pod.ready:
            pod = Pod.objects(self.api).get_or_none(name=name)
            time.sleep(3)
        return pod

    def delete_pod(self, name: str):
        pod = Pod.objects(self.api).get_by_name(name)
        pod.delete()
        time.sleep(3)
