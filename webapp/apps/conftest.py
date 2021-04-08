import binascii
import os
import json
import datetime
import functools
import re

import requests
import requests_mock
import pytest
import stripe
import paramtools as pt

from django import forms
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils.timezone import make_aware
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from guardian.shortcuts import assign_perm

import webapp.settings
import webapp.apps.users.models
from webapp.settings import USE_STRIPE
from webapp.apps.billing.models import (
    Customer,
    Product,
    Plan,
    Subscription,
    SubscriptionItem,
    create_pro_billing_objects,
)
from webapp.apps.users.models import Profile, Project, Cluster, Tag, cryptkeeper
from webapp.apps.comp.model_parameters import ModelParameters
from webapp.apps.comp.models import Inputs, Simulation


stripe.api_key = os.environ.get("STRIPE_SECRET")

###########################User/Billing Fixtures###############################
from django.conf import settings


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        User = get_user_model()
        modeler = User.objects.create_user(
            username="modeler", email="modeler@email.com", password="modeler2222"
        )

        sponsor = User.objects.create_user(
            username="sponsor", email="sponsor@email.com", password="sponsor2222"
        )

        hdoupe = User.objects.create_user(
            username="hdoupe", email="hdoupe@email.com", password="hdoupe2222"
        )

        # User for pushing outputs from the workers to the webapp.
        comp_api_user = User.objects.create_user(
            username="comp-api-user",
            email="comp-api-user@email.com",
            password="heyhey2222",
        )

        webapp.settings.DEFAULT_CLUSTER_USER = "comp-api-user"
        webapp.apps.users.models.DEFAULT_CLUSTER_USER = "comp-api-user"
        for u in [modeler, sponsor, hdoupe, comp_api_user]:
            Token.objects.create(user=u)
            Profile.objects.create(user=u, is_active=True)

        comp_api_user.refresh_from_db()

        cluster = Cluster.objects.create(
            service_account=comp_api_user.profile,
            url="http://scheduler",
            jwt_secret=cryptkeeper.encrypt(binascii.hexlify(os.urandom(32)).decode()),
            version="v0",
        )

        common = {
            "description": "[Matchups](https://github.com/hdoupe/Matchups) provides pitch data on pitcher and batter matchups.. Select a date range using the format YYYY-MM-DD. Keep in mind that Matchups only provides data on matchups going back to 2008. Two datasets are offered to run this model: one that only has the most recent season, 2018, and one that contains data on every single pitch going back to 2008. Next, select your favorite pitcher and some batters who he's faced in the past. Click submit to start analyzing the selected matchups!",
            "oneliner": "oneliner",
            "repo_url": "https://github.com/hdoupe/Matchups",
            "exp_task_time": 10,
            "owner": modeler.profile,
            "listed": True,
            "tech": "python-paramtools",
            "cluster": cluster,
        }

        projects = [
            {"title": "Matchups", "owner": hdoupe.profile},
            {"title": "Used-for-testing", "listed": False},
            {"title": "Tax-Brain"},
            {"title": "Used-for-testing-sponsored-apps", "sponsor": sponsor.profile},
            {"title": "Test-Viz", "tech": "dash", "callable_name": "serve"},
        ]

        for project_config in projects:
            project = Project.objects.create(**dict(common, **project_config))
            project.assign_role("admin", project.owner.user)
            assign_perm("write_project", project.cluster.service_account.user, project)
            project.latest_tag = Tag.objects.create(
                project=project, cpu=project.cpu, memory=project.memory, image_tag="v0"
            )
            project.save()

        if USE_STRIPE:
            create_pro_billing_objects()
            for u in [modeler, sponsor, hdoupe]:
                stripe_customer = stripe.Customer.create(
                    email=u.email, source="tok_bypassPending"
                )
                Customer.get_or_construct(stripe_customer.id, u)


@pytest.fixture
def api_client():
    return APIClient()


def use_stripe(func):
    @functools.wraps(func)
    def f(*args, **kwargs):
        if USE_STRIPE:
            return func(*args, **kwargs)
        else:
            return None

    return f


@pytest.fixture
@use_stripe
def stripe_customer():
    """
    Default stripe.Customer object where token is valid and
    charge goes through
    """
    customer = stripe.Customer.create(
        email="tester@example.com", source="tok_bypassPending"
    )
    return customer


@pytest.fixture
def password():
    return "heyhey2222"


@pytest.fixture
def user(db, password):
    User = get_user_model()
    user = User.objects.create_user(
        username="tester", email="tester@email.com", password=password
    )
    Token.objects.create(user=user)
    assert user.username
    assert user.email
    assert user.password
    assert user.auth_token
    return user


@pytest.fixture
@use_stripe
def basiccustomer(db, stripe_customer, user):
    customer, _ = Customer.get_or_construct(stripe_customer.id, user)
    return customer


@pytest.fixture
@use_stripe
def customer(db, basiccustomer):
    return basiccustomer


@pytest.fixture
def profile(db, user, customer):
    if customer:
        return Profile.objects.create(user=customer.user, is_active=True)
    else:
        return Profile.objects.create(user=user, is_active=True)


@pytest.fixture
def profile_w_mockcustomer(db, password):
    User = get_user_model()
    user = User.objects.create_user(
        username="mockcustomer", email="mockcustomer@email.com", password=password
    )
    Token.objects.create(user=user)
    # profile has a customer.
    customer = Customer.objects.create(
        stripe_id="hello world",
        livemode=False,
        user=user,
        account_balance=0,
        currency="usd",
        delinquent=False,
        default_source="123",
        metadata={},
    )
    return Profile.objects.create(user=customer.user, is_active=True)


@pytest.fixture
def free_profile(db, profile, profile_w_mockcustomer):
    mock_cp = lambda: {"name": "free", "plan_duration": None}
    profile_w_mockcustomer.user.customer.current_plan = mock_cp
    return profile_w_mockcustomer


@pytest.fixture
def pro_profile(db, profile, profile_w_mockcustomer):
    if getattr(profile.user, "customer", None):
        product = Product.objects.get(name="Compute Studio Subscription")
        plan = product.plans.get(nickname="Monthly Pro Plan")
        profile.user.customer.update_plan(plan)
        return profile
    else:
        mock_cp = lambda: {"name": "pro", "plan_duration": "monthly"}
        profile_w_mockcustomer.user.customer.current_plan = mock_cp
        return profile_w_mockcustomer


@pytest.fixture
def customer_pro_by_default(monkeypatch):
    # This test is only valid if the C/S instance is using the Stripe/Customer
    # framework
    try:
        from webapp.apps.billing.models import Customer
    except ImportError:
        from webapp.settings import HAS_USAGE_RESTRICTIONS

        assert HAS_USAGE_RESTRICTIONS
        return

    monkeypatch.setattr(Customer, "plan_in_nostripe_mode", "pro")


@pytest.fixture
def plans(db):
    plans = Plan.objects.filter(product__name="modeler/Used-for-testing")
    return plans


@pytest.fixture
def licensed_plan(db, plans):
    assert len(plans) > 0
    return plans.get(usage_type="licensed")


@pytest.fixture
def metered_plan(db, plans):
    assert len(plans) > 0
    return plans.get(usage_type="metered")


@pytest.fixture
def subscription(db, customer, licensed_plan, metered_plan):
    stripe_subscription = Subscription.create_stripe_object(
        customer, [licensed_plan, metered_plan]
    )
    assert stripe_subscription

    subscription, _ = Subscription.get_or_construct(
        stripe_subscription.id, customer=customer, plans=[licensed_plan, metered_plan]
    )

    for raw_si in stripe_subscription["items"]["data"]:
        stripe_si = SubscriptionItem.get_stripe_object(raw_si["id"])
        plan, created = Plan.get_or_construct(raw_si["plan"]["id"])
        assert not created
        si, created = SubscriptionItem.get_or_construct(
            stripe_si.id, plan, subscription
        )
        assert si

    return subscription


@pytest.fixture
def project(db):
    return Project.objects.get(title="Used-for-testing")


@pytest.fixture
def viz_project(db):
    return Project.objects.get(title="Test-Viz")


@pytest.fixture
def test_models(db, profile):
    project = Project.objects.get(title="Used-for-testing")
    inputs = Inputs.objects.create(project=project)
    obj0 = Simulation.objects.create(
        owner=profile,
        project=project,
        run_time=10,
        run_cost=1,
        inputs=inputs,
        creation_date=make_aware(datetime.datetime(2019, 2, 1)),
        model_pk=Simulation.objects.next_model_pk(project),
        is_public=False,
    )
    assert obj0

    project = Project.objects.get(title="Used-for-testing-sponsored-apps")
    inputs = Inputs.objects.create(project=project)
    obj1 = Simulation.objects.create(
        owner=profile,
        sponsor=project.sponsor,
        project=project,
        run_time=10,
        run_cost=1,
        inputs=inputs,
        creation_date=make_aware(datetime.datetime(2019, 1, 1)),
        model_pk=Simulation.objects.next_model_pk(project),
        is_public=False,
    )
    assert obj1
    return obj0, obj1


############################Core Fixtures###############################


@pytest.fixture
def comp_inputs_json():
    path = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(path, "comp/tests/inputs.json")) as f:
        return json.loads(f.read())


@pytest.fixture
def meta_param_dict(comp_inputs_json):
    return comp_inputs_json["meta_param_dict"]


@pytest.fixture
def meta_param(meta_param_dict):
    class metaparams(pt.Parameters):
        defaults = meta_param_dict

    return metaparams()


@pytest.fixture
def valid_meta_params(meta_param, meta_param_dict):
    return meta_param.specification(meta_data=False, serializable=True)


@pytest.fixture
def get_inputs(comp_inputs_json):
    schema = {
        "schema": {
            "additional_members": {
                "section_1": {"type": "str"},
                "section_2": {"type": "str"},
            }
        }
    }

    class Params1(pt.Parameters):
        defaults = dict(comp_inputs_json["model_params"]["majorsection1"], **schema)

    class Params2(pt.Parameters):
        defaults = dict(comp_inputs_json["model_params"]["majorsection2"], **schema)

    class MetaParams(pt.Parameters):
        array_first = True
        defaults = comp_inputs_json["meta_param_dict"]

    p1 = Params1().specification(serializable=True, meta_data=True)
    p2 = Params2().specification(serializable=True, meta_data=True)
    mp = MetaParams().specification(serializable=True, meta_data=True)
    return {
        "meta_parameters": mp,
        "model_parameters": {"majorsection1": p1, "majorsection2": p2},
    }


@pytest.fixture
def comp_api_user(db):
    return Profile.objects.get(user__username="comp-api-user")


####### Mock requests to kubernetes cluster ##########


@pytest.fixture
def mock_post_to_cluster():
    matcher = re.compile(Cluster.objects.default().url)
    with requests_mock.Mocker(real_http=True) as mock:
        mock.register_uri("POST", matcher, json={})
        mock.register_uri("GET", matcher, json={})
        yield


@pytest.fixture
def mock_deployments_requests_to_cluster():
    matcher = re.compile(f"{Cluster.objects.default().url}/deployments*")
    print(matcher)
    print(f"{Cluster.objects.default().url}/deployments*")
    with requests_mock.Mocker(real_http=True) as mock:
        mock.register_uri(
            "POST",
            matcher,
            json={
                "deployment": {"ready": True},
                "ingressroute": {"ready": True},
                "svc": {"ready": True},
            },
        )
        mock.register_uri(
            "GET",
            matcher,
            json={
                "deployment": {"ready": True},
                "ingressroute": {"ready": True},
                "svc": {"ready": True},
            },
        )
        mock.register_uri("DELETE", matcher, json={})
        yield
