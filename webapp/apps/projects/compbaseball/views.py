from webapp.apps.core.compute import Compute
from webapp.apps.core.views import InputsView, OutputsView, OutputsDownloadView
from webapp.apps.core.models import Tag, TagOption

from .models import CompbaseballRun
from .displayer import CompbaseballDisplayer
from .submit import CompbaseballSubmit, CompbaseballSave
from .forms import CompbaseballInputsForm
from .meta_parameters import compbaseball_meta_parameters
from .constants import (COMPBASEBALL_VERSION, APP_NAME)


compute = Compute()

class CompbaseballInputsView(InputsView):
    """
    A Django view for serving the default input page, validating the inputs,
    and submitting them to the backend worker nodes.
    """
    form_class = CompbaseballInputsForm
    displayer_class = CompbaseballDisplayer
    submit_class = CompbaseballSubmit
    save_class = CompbaseballSave
    project_name = "CompBaseball"
    app_name = APP_NAME
    meta_parameters = compbaseball_meta_parameters
    meta_options = []
    has_errors = False
    upstream_version = COMPBASEBALL_VERSION


class CompbaseballOutputsView(OutputsView):
    """
    A Django view that polls the backend workers to check whether the result
    is ready yet. Once the result is ready, it is stored in the database and
    served from this view.
    """
    model = CompbaseballRun
    result_header = "CompBaseball Results"
    tags = []
    aggr_tags = [Tag(key="statistic",
                     values=[
                         TagOption(
                            value="mean",
                            title="StatCast Means",
                         ),
                         TagOption(
                             value="std",
                             title="StatCast Standard Dev."
                         )
                     ]
                )]


class CompbaseballOutputsDownloadView(OutputsDownloadView):
    """
    A Django view for downloading the result of the project run.
    """
    model = CompbaseballRun
