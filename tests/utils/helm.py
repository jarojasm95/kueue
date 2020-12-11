import json
import logging
import os
import subprocess
from pathlib import Path

import requests

HELM_VERSION = "v3.4.2"


class Helm:
    def __init__(
        self,
        helm="helm",
        kubeconfig=None,
        default_namespace="default",
        default_chart_dir=Path("helm").absolute(),
        raise_ex_on_err=True,
    ):

        self.helm = helm
        self.kubeconfig = kubeconfig
        self.default_namespace = default_namespace
        self.default_chart_dir = default_chart_dir
        self.raise_ex_on_err = raise_ex_on_err

        self.path = Path(".venv/bin")
        self.path.mkdir(parents=True, exist_ok=True)
        self.helm_path = self.path / "helm"

    def ensure_helm(self):
        if not self.helm_path.exists():
            url = os.getenv(
                "HELM_INSTALL_SCRIPT_URL",
                "https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3",
            )
            logging.info(f"Downloading {url}..")
            install_script = self.helm_path.with_suffix(".sh")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with install_script.open("wb") as fd:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            fd.write(chunk)
            install_script.chmod(0o700)
            subprocess.check_call(
                [install_script, "--version", HELM_VERSION, "--no-sudo"],
                env={
                    "HELM_INSTALL_DIR": self.path.absolute(),
                    "BINARY_NAME": self.helm,
                    "PATH": str(self.path.absolute()) + ":" + os.environ["PATH"],
                },
            )
            os.remove(install_script)

    def _run_command(self, command, **kwargs):

        final_command = list(command)

        if "kubeconfig" in kwargs and kwargs["kubeconfig"]:
            final_command.append("--kubeconfig %s" % kwargs["kubeconfig"])
        else:
            final_command.append("--kubeconfig %s" % self.kubeconfig)

        if "namespace" in kwargs and kwargs["namespace"]:
            final_command.append("--namespace %s" % kwargs["namespace"])
        else:
            final_command.append("--namespace %s" % self.default_namespace)

        if kwargs.get("wait"):
            final_command.append("--wait")

        raise_ex_on_err = self.raise_ex_on_err
        if "raise_ex_on_err" in kwargs:
            raise_ex_on_err = kwargs["raise_ex_on_err"]

        json_mode = False
        if "json" in kwargs and kwargs["json"]:
            final_command.append("-o json")
            json_mode = True

        final_command = " ".join(final_command)

        logging.debug("running command: %s" % final_command)

        result = subprocess.run(
            final_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

        err = None
        if result.stderr.decode("utf-8") != "":
            err = result.stderr.decode("utf-8")

        if raise_ex_on_err:
            result.check_returncode()

        data = None
        if not err:
            if json_mode:
                data = json.loads(result.stdout)
            else:
                data = result.stdout.decode("utf-8")

        return data, err

    def search(self, keyword, **kwargs):

        command = [self.helm, "search", "repo", keyword]
        return self._run_command(command, json=True, **kwargs)

    def pull(self, chart_name, **kwargs):

        chart_dir = self.default_chart_dir
        if "chart_dir" in kwargs:
            chart_dir = kwargs["chart_dir"]

        command = [self.helm, "pull", chart_name, "--untar", "--untardir", chart_dir]
        return self._run_command(command, **kwargs)

    def list(self, **kwargs):

        command = [self.helm, "list"]
        return self._run_command(command, json=True, **kwargs)

    def install(self, release_name, chart_name, upgrade=False, **kwargs):

        chart_dir = self.default_chart_dir
        if "chart_dir" in kwargs:
            chart_dir = kwargs["chart_dir"]

        command = [self.helm]

        if upgrade:
            command.append("upgrade")
            command.append("-i")
        else:
            command.append("install")

        command.append(release_name)

        if "/" in chart_name:
            command.append(chart_name)
        else:
            command.append("%s/%s" % (chart_dir, chart_name))

        return self._run_command(command, json=True, **kwargs)

    def uninstall(self, release_name, **kwargs):

        command = [self.helm, "uninstall", release_name]
        return self._run_command(command, **kwargs)

    def status(self, release_name, **kwargs):

        command = [self.helm, "status", release_name]
        return self._run_command(command, json=True, **kwargs)

    def get_values(self, release_name, **kwargs):

        command = [self.helm, "get", "values", release_name, "--all"]
        return self._run_command(command, json=True, **kwargs)

    def show_info(self, chart_name, component=all, **kwargs):

        chart_dir = self.default_chart_dir
        if "chart_dir" in kwargs:
            chart_dir = kwargs["chart_dir"]

        command = [self.helm, "show", component]

        if "/" in chart_name:
            command.append(chart_name)
        else:
            command.append("%s/%s" % (chart_dir, chart_name))

        return self._run_command(command, **kwargs)

    def repo_list(self, **kwargs):

        command = [self.helm, "repo", "list"]

        data, err = self._run_command(command, json=True, **kwargs)
        if data is None:
            data = []  # workaround for an Helm bug, fixed in the next release
        return data, err

    def repo_add(self, name, url, username=None, password=None, **kwargs):

        command = [self.helm, "repo", "add", name, url]
        if username is not None and password is not None:
            command = command + ["--username", username, "--password", password]
        return self._run_command(command, **kwargs)

    def repo_remove(self, name, **kwargs):

        command = [self.helm, "repo", "remove", name]
        return self._run_command(command, **kwargs)

    def repo_update(self, **kwargs):

        command = [self.helm, "repo", "update"]
        return self._run_command(command, **kwargs)
