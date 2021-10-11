import json
import re
from django.http.response import HttpResponseNotFound

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination

# from webapp.settings import DEBUG

from webapp.settings import USE_STRIPE
from webapp.apps.users.auth import ClusterAuthentication, ClientOAuth2Authentication
from webapp.apps.users.exceptions import PrivateAppException
from webapp.apps.users.models import (
    Build,
    Project,
    Cluster,
    Deployment,
    EmbedApproval,
    Tag,
    is_profile_active,
    get_project_or_404,
    projects_with_access,
)
from webapp.apps.users.permissions import StrictRequiresActive, RequiresActive

from webapp.apps.users.serializers import (
    BuildSerializer,
    ClusterBuildSerializer,
    ProjectSerializer,
    ProjectWithVersionSerializer,
    TagSerializer,
    TagUpdateSerializer,
    EmbedApprovalSerializer,
    DeploymentSerializer,
)
from .utils import title_fixup

User = get_user_model()


def send_new_app_email(user, model, status_url):
    try:
        send_mail(
            f"{user.username} created a new app on Compute Studio!",
            (
                f"Your app, {model.title}, has been created. When you are ready, you can finish "
                f"connecting your app at {status_url}.\n\n"
                f"If you have any questions, please feel welcome to send me an email at "
                f"hank@compute.studio."
            ),
            "notifications@compute.studio",
            list({user.email, "hank@compute.studio"}),
            fail_silently=False,
        )
    # Http 401 exception if mail credentials are not set up.
    except Exception:
        pass


def send_updated_app_email(user, model, status_url):
    try:
        send_mail(
            f"{model} has been updated",
            (
                f"Your app, {model.title}, will be updated or you will have feedback within "
                f"the next 24 hours. Check the status of the update at "
                f"{status_url}."
            ),
            "notifications@compute.studio",
            list({user.email, "hank@compute.studio"}),
            fail_silently=False,
        )
    # Http 401 exception if mail credentials are not set up.
    except Exception:
        pass


def send_app_ready_email(user, model, status_url):
    try:
        send_mail(
            f"{model} is ready to be connected on Compute Studio!",
            (
                f"Your app, {model.title}, will be live or you will have feedback within "
                f"the next 24 hours. Check the status of the update at "
                f"{status_url}."
            ),
            "notifications@compute.studio",
            list({user.email, "hank@compute.studio"}),
            fail_silently=False,
        )
    # Http 401 exception if mail credentials are not set up.
    except Exception:
        pass


class GetProjectMixin:
    def get_object(self, username, title, **kwargs):
        return get_project_or_404(
            Project.objects.all(),
            user=self.request.user,
            title__iexact=title,
            owner__user__username__iexact=username,
        )


class ProjectView(View):
    template_name = "publish/publish.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class ProjectDetailView(GetProjectMixin, View):
    template_name = "publish/publish.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(**kwargs)
        return render(request, self.template_name, context={"object": self.object})


class ProjectReactView(GetProjectMixin, View):
    template_name = "publish/publish.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(**kwargs)
        if not self.object.has_write_access(request.user):
            raise PermissionDenied()
        return render(request, self.template_name, context={"object": self.object})


class BuildDetailReactView(GetProjectMixin, View):
    template_name = "publish/publish.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(**kwargs)
        if not self.object.has_write_access(request.user):
            raise PermissionDenied()
        get_object_or_404(Build, project=self.object, pk=kwargs["id"])
        return render(request, self.template_name, context={"object": self.object})


class ProjectDetailAPIView(GetProjectMixin, APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )

    def get(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        serializer = ProjectSerializer(project, context={"request": request})
        data = serializer.data
        return Response(data)

    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        project = self.get_object(**kwargs)
        if not project.has_write_access(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        previous_status = project.status
        serializer = ProjectSerializer(project, data=request.data)
        try:
            is_valid = serializer.is_valid()
        except PrivateAppException as e:
            return Response(
                {e.resource: e.todict()}, status=status.HTTP_400_BAD_REQUEST
            )
        if is_valid:
            model = serializer.save()
            new_status = model.status
            Project.objects.sync_project_with_workers(
                ProjectSerializer(model).data, model.cluster
            )
            status_url = request.build_absolute_uri(model.app_url)
            if previous_status != "staging" and new_status == "staging":
                send_app_ready_email(
                    request.user, model, status_url,
                )
            elif previous_status in ("staging", "running"):
                send_updated_app_email(request.user, model, status_url)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectResultsPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 10


class ProjectAPIView(generics.ListAPIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
        ClusterAuthentication,
    )
    api_user = User.objects.get(username="comp-api-user")

    serializer_class = ProjectSerializer
    pagination_class = ProjectResultsPagination

    def get_queryset(self):
        return projects_with_access(self.request.user)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            serializer = ProjectSerializer(
                data=request.POST, context={"request": request}
            )
            is_valid = serializer.is_valid()
            if is_valid:
                title = title_fixup(serializer.validated_data["title"])
                username = request.user.username
                print("creating", title, username)
                if (
                    Project.objects.filter(
                        owner__user__username__iexact=username, title__iexact=title
                    ).count()
                    > 0
                ):
                    return Response(
                        {"project_exists": f"{username}/{title} already exists."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    model = serializer.save(
                        owner=request.user.profile,
                        title=title,
                        cluster=Cluster.objects.default(),
                    )
                except PrivateAppException as e:
                    return Response(
                        {e.resource: e.todict()}, status=status.HTTP_400_BAD_REQUEST
                    )
                status_url = request.build_absolute_uri(model.app_url)
                send_new_app_email(request.user, model, status_url)
                model.assign_role("write", self.api_user)
                Project.objects.sync_project_with_workers(
                    ProjectSerializer(model).data, model.cluster
                )
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                print("error", request, serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


class TagsAPIView(GetProjectMixin, APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    permission_classes = (StrictRequiresActive,)

    def get(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        if not project.has_write_access(request.user):
            raise APIPermissionDenied()
        return Response(
            {
                "staging_tag": TagSerializer(instance=project.staging_tag).data,
                "latest_tag": TagSerializer(instance=project.latest_tag).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        if not project.has_write_access(request.user):
            raise APIPermissionDenied()
        serializer = TagUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if data.get("staging_tag") is not None:
            tag, _ = Tag.objects.get_or_create(
                project=project,
                image_tag=data.get("staging_tag"),
                version=data.get("version"),
                defaults=dict(cpu=project.cpu, memory=project.memory),
            )
            project.staging_tag = tag
        elif "staging_tag" in data:
            project.staging_tag = None

        if data.get("latest_tag") is not None:
            tag, _ = Tag.objects.get_or_create(
                project=project,
                image_tag=data.get("latest_tag"),
                version=data.get("version"),
                defaults=dict(cpu=project.cpu, memory=project.memory),
            )
            previous_tag = project.latest_tag
            project.latest_tag = tag

            if previous_tag:
                for deployment in project.deployments.filter(
                    status__in=["creating", "running"], tag=previous_tag
                ):
                    try:
                        deployment.delete_deployment()
                    except Exception as e:
                        print(
                            "Exception when deleting deployment",
                            deployment.public_name,
                            project,
                            e,
                        )

        project.save()

        return Response(
            {
                "staging_tag": TagSerializer(instance=project.staging_tag).data,
                "latest_tag": TagSerializer(instance=project.latest_tag).data,
            },
            status=status.HTTP_200_OK,
        )


class RecentModelsAPIView(generics.ListAPIView):
    permission_classes = (StrictRequiresActive,)
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    queryset = None
    serializer_class = ProjectSerializer
    n_recent = 7

    def get_queryset(self):
        return self.request.user.profile.recent_models(limit=self.n_recent)


class ModelsAPIView(generics.ListAPIView):
    permission_classes = (StrictRequiresActive,)
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    queryset = Project.objects.all().order_by("-pk")
    serializer_class = ProjectWithVersionSerializer

    def get_queryset(self):
        return self.queryset.filter(owner__user=self.request.user)


class ProfileModelsAPIView(generics.ListAPIView):
    permission_classes = (RequiresActive,)
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    queryset = Project.objects.all().order_by("-pk")
    serializer_class = ProjectWithVersionSerializer

    def get_queryset(self):
        username = self.request.parser_context["kwargs"].get("username", None)
        user = get_object_or_404(get_user_model(), username__iexact=username)
        return self.queryset.filter(
            owner__user=user,
            listed=True,
            pk__in=projects_with_access(self.request.user),
        )


class BuildView(generics.ListCreateAPIView):
    permission_classes = (RequiresActive,)
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    queryset = Build.objects.all()
    serializer_class = BuildSerializer

    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["status", "status__in"]
    ordering_fields = ["created_at", "project__title", "project__owner"]
    ordering = ["-created_at"]

    def get_project(self, username, title, **kwargs):
        return get_project_or_404(
            Project.objects.all(),
            user=self.request.user,
            title__iexact=title,
            owner__user__username__iexact=username,
        )

    def post(self, request, *args, **kwargs):
        project = self.get_project(**kwargs)
        if project.builds.filter(
            ~Q(status__in=["success", "failure", "cancelled"])
        ).count():
            return Response({"errors": "Only one build can be run at a time."})
        build = Build.objects.create(project=project)
        build.start()
        return Response(
            BuildSerializer(instance=build).data, status=status.HTTP_201_CREATED
        )

    def get(self, request, *args, **kwargs):
        project = self.get_project(**kwargs)
        queryset = self.queryset.filter(project=project)
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BuildDetailView(APIView):
    permission_classes = (RequiresActive,)
    authentication_classes = (
        ClientOAuth2Authentication,
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )

    def is_using_cluster_id(self):
        return self.request.query_params.get("cluster_id", None) == "true"

    def get_object(self, **kwargs):
        query_kwargs = {}
        query_params = self.request.query_params
        if self.is_using_cluster_id():
            query_kwargs["cluster_build_id"] = kwargs["id"]
        else:
            query_kwargs["id"] = kwargs["id"]

        return get_object_or_404(
            Build.objects.prefetch_related("project"), **query_kwargs
        )

    def get(self, request, *args, **kwargs):
        build = self.get_object(**kwargs)
        if not build.project.has_write_access(request.user):
            raise Http404("Build not found.")
        build.refresh_status(
            force_reload=request.query_params.get("force_reload", None) == "true"
        )
        build.refresh_from_db()
        return Response(BuildSerializer(instance=build).data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        build = self.get_object(**kwargs)
        if not build.project.has_write_access(request.user):
            raise Http404("Build not found.")

        print("is_using_cluster_id", self.is_using_cluster_id())
        if self.is_using_cluster_id():
            serializer = ClusterBuildSerializer(instance=build, data=request.data)
        else:
            serializer = BuildSerializer(instance=build, data=request.data)

        if serializer.is_valid():
            instance = serializer.save()
            instance.refresh_from_db()
            return Response(
                BuildSerializer(instance=instance).data, status=status.HTTP_200_OK
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagPromoteView(APIView):
    permission_classes = (RequiresActive,)
    authentication_classes = (
        ClientOAuth2Authentication,
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )

    def post(self, request, *args, **kwargs):
        build = self.get_object(**kwargs)
        if not build.project.has_write_access(request.user):
            raise Http404("Build not found.")

        if getattr(build, "tag", None) is None:
            return Response(
                {"errors": "Build not successful and cannot be promoted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        build.project.latest_tag = build.tag
        build.project.save()

        return Response(BuildSerializer(instance=build).data, status=status.HTTP_200_OK)

    def get(self, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class EmbedApprovalView(GetProjectMixin, APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    permission_classes = (StrictRequiresActive,)

    def post(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        if project.tech == "python-paramtools":
            return Response(
                {"tech": "Unable to embed ParamTools-based apps, yet. Stay tuned."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = EmbedApprovalSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            name = serializer.validated_data["name"]
            if EmbedApproval.objects.filter(project=project, name=name).count() > 0:
                return Response(
                    {"exists": f"Embed Approval for {name} already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            model = serializer.save(project=project, owner=request.user.profile)
            return Response(
                EmbedApprovalSerializer(instance=model).data, status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        eas = EmbedApproval.objects.filter(
            project__owner__user__username__iexact=kwargs["username"],
            project__title__iexact=kwargs["title"],
            owner=request.user.profile,
        )
        serializer = EmbedApprovalSerializer(eas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmbedApprovalDetailView(GetProjectMixin, APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    permission_classes = (StrictRequiresActive,)

    def get(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        ea = EmbedApproval.objects.get(project=project, name__iexact=kwargs["ea_name"],)

        # Throw 404 if user does not have access.
        if ea.owner != request.user.profile:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = EmbedApprovalSerializer(ea)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        ea = EmbedApproval.objects.get(project=project, name__iexact=kwargs["ea_name"],)

        # Throw 404 if user does not have access.
        if ea.owner != request.user.profile:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = EmbedApprovalSerializer(
            ea, data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            name = serializer.validated_data["name"]
            if (
                name != ea.name
                and EmbedApproval.objects.filter(project=ea.project, name=name).count()
                > 0
            ):
                return Response(
                    {"exists": f"Embed Approval for {name} already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            model = serializer.save(project=ea.project, owner=request.user.profile)
            return Response(
                EmbedApprovalSerializer(instance=model).data, status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)
        ea = EmbedApproval.objects.get(project=project, name__iexact=kwargs["ea_name"],)

        # Throw 404 if user does not have access.
        if ea.owner != request.user.profile:
            return Response(status=status.HTTP_404_NOT_FOUND)

        ea.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeploymentsView(generics.ListAPIView):
    permission_classes = (StrictRequiresActive,)
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at"]
    ordering = ["created_at"]
    queryset = Deployment.objects.filter(
        deleted_at__isnull=True, status__in=["creating", "running"]
    )
    serializer_class = DeploymentSerializer

    def get_queryset(self):
        return self.queryset.filter(
            project__cluster__service_account__user=self.request.user
        )


class DeploymentsDetailView(GetProjectMixin, APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )

    permission_classes = (RequiresActive,)

    def get(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)

        status_query = request.query_params.get("status", None)
        ping = request.query_params.get("ping", None)
        if status_query is None:
            status_kwarg = {"status__in": ["creating", "running"]}
        else:
            status_kwarg = {"status": status_query}

        deployment = get_object_or_404(
            Deployment,
            name__iexact=kwargs["dep_name"],
            project=project,
            deleted_at__isnull=True,
            **status_kwarg,
        )

        if ping is None:
            deployment.load()
        else:
            deployment.ping()

        return Response(
            DeploymentSerializer(deployment).data, status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        project = self.get_object(**kwargs)

        if not project.has_write_access(request.user):
            raise APIPermissionDenied()

        deployment = get_object_or_404(
            Deployment,
            name__iexact=kwargs["dep_name"],
            project=project,
            deleted_at__isnull=True,
            status__in=["creating", "running"],
        )

        deployment.delete_deployment()

        return Response(status=status.HTTP_204_NO_CONTENT)


class DeploymentsIdView(APIView):
    authentication_classes = (
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    )

    permission_classes = (RequiresActive,)

    def get(self, request, *args, **kwargs):
        ping = request.query_params.get("ping", None)
        deployment = get_object_or_404(
            Deployment.objects.prefetch_related("project"), pk=kwargs["id"]
        )
        if not deployment.project.has_read_access(request.user):
            raise Http404()

        if ping is None:
            deployment.load()
        else:
            deployment.ping()

        return Response(
            DeploymentSerializer(deployment).data, status=status.HTTP_200_OK,
        )
