from pathlib import Path
from typing import Optional

from pytest_kind import KindCluster as KC


class KindCluster(KC):
    def __init__(self, name: str, kubeconfig: Optional[Path] = None):
        self.name = name
        self.kubeconfig = kubeconfig
        self.path = Path(".venv/bin").absolute()
        self.path.mkdir(parents=True, exist_ok=True)
        self.kind_path = self.path / "kind"
        self.kubectl_path = self.path / "kubectl"
