import argparse
from datetime import datetime
import json
import os
import uuid

from kubernetes import config as kconfig
import marshmallow as ma
import redis
import tornado.ioloop
import tornado.web

from cs_workers.utils import hash_projects, redis_conn_from_env
from cs_workers.models.clients import job, api_task, server
from cs_workers.config import ModelConfig
from cs_workers.services.serializers import Payload, Deployment
from cs_workers.services.auth import AuthApi, authenticate_request, all_users

PROJECT = os.environ.get("PROJECT")

redis_conn = dict(
    username=os.environ.get("REDIS_USER"),
    password=os.environ.get("REDIS_PW"),
    **redis_conn_from_env(),
)


incluster = os.environ.get("KUBERNETES_SERVICE_HOST", False) is not False


class Scheduler(tornado.web.RequestHandler):
    def initialize(self, config=None, rclient=None):
        self.config = config
        self.rclient = rclient

    def save_job_info(self, job_id):
        self.rclient.set(
            f"jobinfo-{job_id}",
            json.dumps(
                {
                    "cluster_user": self.user.username,
                    "created_at": str(datetime.utcnow()),
                }
            ),
        )

    async def prepare(self):
        self.user = authenticate_request(self.request)
        if self.user is None or not getattr(self.user, "approved", False):
            raise tornado.web.HTTPError(403)

    async def post(self, owner, title):
        print("POST -- /", owner, title)
        if not self.request.body:
            return
        payload = Payload().loads(self.request.body.decode("utf-8"))

        try:
            project = self.config[self.user.username].get_project(owner, title)
        except KeyError:
            self.set_status(404)
            return

        task_id = payload.get("task_id")
        if task_id is None:
            task_id = uuid.uuid4()
        task_id = str(task_id)
        task_name = payload["task_name"]
        task_kwargs = payload["task_kwargs"]

        if task_name in ("version", "defaults"):
            client = api_task.APITask(
                owner, title, task_id=task_id, task_name=task_name, **task_kwargs,
            )
            resp = await client.create(asynchronous=False)
            assert resp.status_code == 200, f"Got code: {resp.status_code}"
            data = resp.json()
        elif task_name in ("parse",):
            client = api_task.APITask(
                owner, title, task_id=task_id, task_name=task_name, **task_kwargs,
            )
            resp = await client.create(asynchronous=True)
            assert resp.status_code == 200, f"Got code: {resp.status_code}"

            data = resp.json()
            self.save_job_info(data["task_id"])
        elif task_name == "sim":
            tag = payload["tag"]
            client = job.Job(
                PROJECT,
                owner,
                title,
                tag=tag,
                model_config=project,
                job_id=task_id,
                job_kwargs=payload["task_kwargs"],
                rclient=self.rclient,
            )
            client.create()
            data = {"task_id": client.job_id}
            self.save_job_info(client.job_id)
        else:
            self.set_status(404)
            return

        self.write(data)


class SyncProjects(tornado.web.RequestHandler):
    def initialize(self, config=None, rclient=None):
        self.config = config
        self.rclient = rclient

    async def prepare(self):
        self.user = authenticate_request(self.request)
        if self.user is None or not getattr(self.user, "approved", False):
            raise tornado.web.HTTPError(403)

    def post(self):
        print("POST -- /sync/")
        data = json.loads(self.request.body.decode("utf-8"))
        projects = hash_projects(data)
        self.config[self.user.username].set_projects(projects=projects)
        self.set_status(200)


class DeploymentsDetailApi(tornado.web.RequestHandler):
    def initialize(self, config=None, rclient=None):
        self.config = config
        self.rclient = rclient

    async def prepare(self):
        self.user = authenticate_request(self.request)
        if self.user is None or not getattr(self.user, "approved", False):
            raise tornado.web.HTTPError(403)

    def get(self, owner, title, deployment_name):
        print("GET --", f"/deployments/{owner}/{title}/{deployment_name}/")
        try:
            project = self.config[self.user.username].get_project(owner, title)
        except KeyError:
            self.set_status(404)
            return

        # TODO: support more techs
        if project["tech"] in ("dash", "bokeh"):
            viz = server.Server(
                project=PROJECT,
                owner=project["owner"],
                title=project["title"],
                tag=None,
                model_config=project,
                callable_name=project["callable_name"],
                deployment_name=deployment_name,
                incluster=incluster,
            )
            self.write(viz.ready_stats())
            self.set_status(200)
            return
        else:
            self.set_status(400)
            self.write({"tech": f"Unsuported tech: {project['tech']}"})
            return

    def delete(self, owner, title, deployment_name):
        print("DELETE --", f"/deployments/{owner}/{title}/{deployment_name}/")
        try:
            project = self.config[self.user.username].get_project(owner, title)
        except KeyError:
            self.set_status(404)
            return

        # TODO: support more techs
        if project["tech"] in ("dash", "bokeh"):
            viz = server.Server(
                project=PROJECT,
                owner=project["owner"],
                title=project["title"],
                tag=None,
                model_config=project,
                callable_name=project["callable_name"],
                deployment_name=deployment_name,
                incluster=incluster,
            )
            self.write(viz.delete())
            self.set_status(200)
            return
        else:
            self.set_status(400)
            self.write({"tech": f"Unsuported tech: {project['tech']}"})
            return


class DeploymentsApi(tornado.web.RequestHandler):
    def initialize(self, config=None, rclient=None):
        self.config = config
        self.rclient = rclient

    async def prepare(self):
        self.user = authenticate_request(self.request)
        if self.user is None or not getattr(self.user, "approved", False):
            raise tornado.web.HTTPError(403)

    def post(self, owner, title):
        print("POST --", f"/deployments/{owner}/{title}/")
        try:
            project = self.config[self.user.username].get_project(owner, title)
        except KeyError:
            self.set_status(404)
            return

        if not self.request.body:
            self.write({"errors": ["No content received."]})
            self.set_status(400)
            return

        try:
            data = Deployment().loads(self.request.body.decode("utf-8"))
        except ma.ValidationError as ve:
            self.write(ve.messages)
            self.set_status(400)
            return

        # TODO: support more techs
        if project["tech"] in ("dash", "bokeh"):
            viz = server.Server(
                project=PROJECT,
                owner=project["owner"],
                title=project["title"],
                tag=data["tag"],
                model_config=project,
                callable_name=project["callable_name"],
                deployment_name=data["deployment_name"],
                incluster=incluster,
            )
            dep = viz.deployment_from_cluster()
            if dep is not None:
                self.write({"errors": ["Deployment is already running."]})
                self.set_status(400)
                return
            else:
                viz.configure()
                viz.create()
                self.write(viz.ready_stats())
                self.set_status(200)
                return
        else:
            self.set_status(400)
            self.write({"tech": f"Unsuported tech: {project['tech']}"})
            return


def get_app():
    rclient = redis.Redis(**redis_conn)
    config = {}
    for user in all_users():
        print(f"loading data for {user.username} at {user.url}")
        try:
            user_config = ModelConfig(
                PROJECT,
                cs_url=user.url,
                cs_auth_headers=user.headers(),
                rclient=rclient,
            )
            user_config.set_projects()
            config[user.username] = user_config
        # Likely to be a network / connection error.
        except Exception:
            import traceback

            traceback.print_exc()

    print("config?:", config)
    assert rclient.hgetall("projects") is not None
    return tornado.web.Application(
        [
            (r"/sync/", SyncProjects, dict(config=config, rclient=rclient),),
            (
                r"/([A-Za-z0-9-]+)/([A-Za-z0-9-]+)/",
                Scheduler,
                dict(config=config, rclient=rclient),
            ),
            (
                r"/deployments/([A-Za-z0-9-]+)/([A-Za-z0-9-]+)/([A-Za-z0-9-]+)/",
                DeploymentsDetailApi,
                dict(config=config, rclient=rclient),
            ),
            (
                r"/deployments/([A-Za-z0-9-]+)/([A-Za-z0-9-]+)/",
                DeploymentsApi,
                dict(config=config, rclient=rclient),
            ),
            (r"/auth/", AuthApi, dict()),
        ],
        debug=True,
        autoreload=True,
    )


def run(args: argparse.Namespace = None):
    port = os.environ.get("PORT", 8888)
    host = os.environ.get("HOST", "localhost")
    print(f"App running on {host}:{port}")
    app = get_app()
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()


def cli(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser(
        "scheduler", description="REST API for running jobs on C/S workers."
    )
    parser.add_argument("--start", required=False, action="store_true")
    parser.set_defaults(func=run)
