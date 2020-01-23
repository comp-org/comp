import pytest
from django.test import RequestFactory

from webapp.apps.users.models import Project
from webapp.apps.pages.context_processors import project_list


@pytest.mark.django_db
def test_project_list(profile):
    factory = RequestFactory()
    mockrequest = factory.get("/")
    mockrequest.user = profile.user

    projs = project_list(mockrequest)
    assert projs
    assert len(projs["project_list"]) == Project.objects.filter(listed=True).count()
    assert isinstance(projs, dict)
    mu = ("hdoupe", "Matchups", "/hdoupe/Matchups/")
    assert mu in projs["project_list"]
