import argparse
import copy
import yaml
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from cs_deploy.config import workers_config
from cs_workers.services.secrets import ServicesSecrets

# from cs_workers.services import scheduler

CURR_PATH = Path(os.path.abspath(os.path.dirname(__file__)))
BASE_PATH = CURR_PATH / ".."


def clean(word):
    return re.sub("[^0-9a-zA-Z]+", "", word).lower()


def run(cmd):
    print(f"Running: {cmd}\n")
    s = time.time()
    res = subprocess.run(cmd, shell=True, check=True)
    f = time.time()
    print(f"\n\tFinished in {f-s} seconds.\n")
    return res


def redis_acl_genpass():
    """
    Redis recommends using ACL GENPASS to generate passwords
    for ACL users. This function attempts to use a local
    redis installation to generate this password automatically.
    """
    import redis

    with redis.Redis(host="localhost", port=6379) as c:
        value = c.acl_genpass()

    return value


class Manager:
    """
    Deploy and manage Compute Studio compute cluster:
        - build, tag, and push the docker images for the flask app and
        compute.studio modeling apps.
        - write k8s config files for the scheduler deployment and the
        compute.studio modeling app deployments.
        - apply k8s config files to an existing compute cluster.

        TODO:
        - teardown, update, add new models to cluster.

    args:
        - config: configuration for the apps powering C/S.
        - tag: image version, defined as [c/s version].[mm][dd].[n]
        - project: GCP project that the compute cluster is under.
        - models (optional): only build a subset of the models in
        the config.

    """

    kubernetes_target = "-"
    cr = "gcr.io"

    def __init__(
        self,
        tag,
        project,
        bucket=None,
        kubernetes_target="kubernetes/",
        use_kind=False,
        cluster_host=None,
        viz_host=None,
    ):
        self.tag = tag
        self.project = project
        self.bucket = bucket
        self.use_kind = use_kind
        self.cluster_host = cluster_host
        self.viz_host = viz_host

        if kubernetes_target is None:
            self.kubernetes_target = Manager.kubernetes_target
        else:
            self.kubernetes_target = kubernetes_target

        self.templates_dir = BASE_PATH / Path("templates")
        self.dockerfiles_dir = BASE_PATH / Path("dockerfiles")

        with open(
            self.templates_dir / "services" / "scheduler-Deployment.template.yaml", "r"
        ) as f:
            self.scheduler_template = yaml.safe_load(f.read())

        with open(
            self.templates_dir / "services" / "scheduler-ingressroute.template.yaml",
            "r",
        ) as f:
            self.scheduler_ir_template = yaml.safe_load(f.read())

        with open(
            self.templates_dir
            / "services"
            / "outputs-processor-Deployment.template.yaml",
            "r",
        ) as f:
            self.outputs_processor_template = yaml.safe_load(f.read())
        with open(
            self.templates_dir / "services" / "outputs-processor-ServiceAccount.yaml",
            "r",
        ) as f:
            self.outputs_processor_serviceaccount = yaml.safe_load(f.read())

        with open(
            self.templates_dir / "services" / "redis-master-Deployment.template.yaml",
            "r",
        ) as f:
            self.redis_master_template = yaml.safe_load(f.read())

        with open(self.templates_dir / "secret.template.yaml", "r") as f:
            self.secret_template = yaml.safe_load(f.read())

        self._redis_secrets = None
        self._secrets = None

    def build(self):
        """
        Build, tag, and push base images for the scheduler app.

        Note: distributed and celerybase are tagged as "latest." All other apps
        pull from either distributed:latest or celerybase:latest.
        """
        distributed = self.dockerfiles_dir / "Dockerfile"
        redis = self.dockerfiles_dir / "Dockerfile.redis"
        outputs_processor = self.dockerfiles_dir / "Dockerfile.outputs_processor"
        scheduler = self.dockerfiles_dir / "Dockerfile.scheduler"

        run(f"docker build -t distributed:latest -f {distributed} ./")
        run(f"docker build -t redis-python:{self.tag} -f {redis} ./")
        run(f"docker build -t outputs_processor:{self.tag} -f {outputs_processor} ./")
        run(f"docker build -t scheduler:{self.tag} -f {scheduler} ./")

    def push(self):
        run(f"docker tag distributed {self.cr}/{self.project}/distributed:latest")
        run(
            f"docker tag redis-python:{self.tag} {self.cr}/{self.project}/redis-python:{self.tag}"
        )

        run(
            f"docker tag outputs_processor:{self.tag} {self.cr}/{self.project}/outputs_processor:{self.tag}"
        )

        run(
            f"docker tag scheduler:{self.tag} {self.cr}/{self.project}/scheduler:{self.tag}"
        )

        if self.use_kind:
            cmd_prefix = "kind load docker-image --name cs --nodes cs-worker"
        else:
            cmd_prefix = "docker push"

        run(f"{cmd_prefix} {self.cr}/{self.project}/distributed:latest")
        run(f"{cmd_prefix} {self.cr}/{self.project}/redis-python:{self.tag}")
        run(f"{cmd_prefix} {self.cr}/{self.project}/outputs_processor:{self.tag}")
        run(f"{cmd_prefix} {self.cr}/{self.project}/scheduler:{self.tag}")

    def config(self, update_redis=False, update_dns=False):
        config_filenames = [
            "scheduler-Service.yaml",
            "scheduler-RBAC.yaml",
            "outputs-processor-Service.yaml",
            "job-cleanup-Job.yaml",
            "job-cleanup-RBAC.yaml",
        ]
        if update_redis:
            config_filenames.append("redis-master-Service.yaml")
        for filename in config_filenames:
            with open(self.templates_dir / "services" / f"{filename}", "r") as f:
                configs = yaml.safe_load_all(f.read())
            for config in configs:
                name = config["metadata"]["name"]
                kind = config["kind"]
                self.write_config(f"{name}-{kind}.yaml", config)
        self.write_scheduler_deployment()
        if update_dns:
            self.write_scheduler_ingressroute()
            self.write_cloudflare_api_token()
        self.write_outputs_processor_deployment()
        self.write_secret()
        if update_redis:
            self.write_redis_deployment()

    def write_scheduler_deployment(self):
        """
        Write scheduler deployment file. Only step is filling in the image uri.
        """
        deployment = copy.deepcopy(self.scheduler_template)
        deployment["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = f"gcr.io/{self.project}/scheduler:{self.tag}"
        deployment["spec"]["template"]["spec"]["containers"][0]["env"] += [
            {"name": "VIZ_HOST", "value": self.viz_host},
        ]
        self.write_config("scheduler-Deployment.yaml", deployment)

        return deployment

    def write_scheduler_ingressroute(self):
        """
        Write scheduler ingressroute file. Only step is filling in the cluster host.
        """
        ir = copy.deepcopy(self.scheduler_ir_template)
        ir["spec"]["routes"][0]["match"] = f"Host(`{self.cluster_host}`)"
        self.write_config("scheduler-ingressroute.yaml", ir)

        return ir

    def write_outputs_processor_deployment(self):
        """
        Write outputs processor deployment file. Only step is filling
        in the image uri.
        """
        deployment = copy.deepcopy(self.outputs_processor_template)
        deployment["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = f"gcr.io/{self.project}/outputs_processor:{self.tag}"

        self.write_config(
            "outputs-processor-ServiceAccount.yaml",
            self.outputs_processor_serviceaccount,
        )
        self.write_config("outputs-processor-Deployment.yaml", deployment)

        return deployment

    def write_redis_deployment(self):
        deployment = copy.deepcopy(self.redis_master_template)
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        container["image"] = f"gcr.io/{self.project}/redis-python:{self.tag}"
        redis_secrets = self.redis_secrets()
        for name, sec in redis_secrets.items():
            if sec is not None:
                container["env"].append(
                    {
                        "name": name,
                        "valueFrom": {
                            "secretKeyRef": {"key": name, "name": "worker-secret"}
                        },
                    }
                )

        if workers_config.get("redis"):
            redis_config = workers_config["redis"]
            assert (
                redis_config.get("provider") == "volume"
            ), f"Got: {redis_config.get('provider', None)}"
            args = redis_config["args"][0]
            deployment["spec"]["template"]["spec"]["volumes"] = args["volumes"]
        self.write_config("redis-master-Deployment.yaml", deployment)

    def write_secret(self):
        assert self.bucket
        assert self.project
        secrets = copy.deepcopy(self.secret_template)
        secrets["stringData"]["BUCKET"] = self.bucket
        secrets["stringData"]["PROJECT"] = self.project
        secrets["stringData"]["CS_CRYPT_KEY"] = workers_config.get(
            "CS_CRYPT_KEY"
        ) or self.secrets.get("CS_CRYPT_KEY")
        redis_secrets = self.redis_secrets()
        for name, sec in redis_secrets.items():
            if sec is not None:
                secrets["stringData"][name] = sec

        self.write_config("secret.yaml", secrets)

    def write_cloudflare_api_token(self):
        api_token = self.secrets.get("CLOUDFLARE_API_TOKEN")

        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "cloudflare-api-token-secret",},
            "type": "Opaque",
            "stringData": {"api-token": api_token},
        }

        self.write_config("cloudflare_token_secret.yaml", secret)

    def write_config(self, filename, config):
        if self.kubernetes_target == "-":
            sys.stdout.write(yaml.dump(config))
            sys.stdout.write("---")
            sys.stdout.write("\n")
        else:
            with open(f"{self.kubernetes_target}/{filename}", "w") as f:
                f.write(yaml.dump(config))

    def redis_secrets(self):
        """
        Return redis ACL user passwords. If they are not in the secret manager,
        try to generate them using a local instance of redis. If this fails,
        they are set to an empty string.
        """
        if self._redis_secrets is not None:
            return self._redis_secrets
        from google.api_core import exceptions

        redis_secrets = dict(
            REDIS_ADMIN_PW="",
            REDIS_EXECUTOR_PW="",
            REDIS_SCHEDULER_PW="",
            REDIS_OUTPUTS_PW="",
        )
        for sec in redis_secrets:
            try:
                value = self.secrets.get(sec)
            except exceptions.NotFound:
                try:
                    value = redis_acl_genpass()
                    self.secrets.set(sec, value)
                except Exception:
                    value = ""
            redis_secrets[sec] = value
        return redis_secrets

    @property
    def secrets(self):
        if self._secrets is None:
            self._secrets = ServicesSecrets(self.project)
        return self._secrets


def manager_from_args(args: argparse.Namespace):
    return Manager(
        tag=args.tag,
        project=args.project,
        bucket=args.bucket,
        kubernetes_target=getattr(args, "out", None),
        use_kind=getattr(args, "use_kind", None),
        cluster_host=getattr(args, "cluster_host", None),
        viz_host=getattr(args, "viz_host", None),
    )


def build(args: argparse.Namespace):
    cluster = manager_from_args(args)
    cluster.build()


def push(args: argparse.Namespace):
    cluster = manager_from_args(args)
    cluster.push()


def config_(args: argparse.Namespace):
    cluster = manager_from_args(args)
    cluster.config(update_redis=args.update_redis, update_dns=args.update_dns)


def port_forward(args: argparse.Namespace):
    run("kubectl port-forward svc/scheduler 8888:80")


def serve(args: argparse.Namespace):
    # scheduler.run()
    pass


def cli(subparsers: argparse._SubParsersAction, config=None, **kwargs):
    parser = subparsers.add_parser("services", aliases=["svc"])
    svc_subparsers = parser.add_subparsers()

    build_parser = svc_subparsers.add_parser("build")
    build_parser.set_defaults(func=build)

    push_parser = svc_subparsers.add_parser("push")
    push_parser.add_argument("--use-kind", action="store_true")
    push_parser.set_defaults(func=push)

    config_parser = svc_subparsers.add_parser("config")
    config_parser.add_argument("--out", "-o")
    config_parser.add_argument("--update-redis", action="store_true")
    config_parser.add_argument(
        "--cluster-host", required=False, default=config.get("CLUSTER_HOST")
    )
    config_parser.add_argument("--update-dns", action="store_true")
    config_parser.set_defaults(func=config_)

    pf_parser = svc_subparsers.add_parser("port-forward")
    pf_parser.set_defaults(func=port_forward)

    serve_parser = svc_subparsers.add_parser("serve")
    serve_parser.set_defaults(func=serve)
