import json
from typing import Literal, TypeAlias

from openforms.submissions.models import Submission

SDKAction: TypeAlias = Literal["resume", "afspraak-annuleren", "cosign", "payment"]


def get_frontend_redirect_url(
    submission: Submission,
    action: SDKAction,
    action_params: dict[str, str] | None = None,
) -> str:
    """Get the frontend redirect URL depending on the action.

    Some actions require arguments to be specified. The frontend will take care of building the right redirection
    based on the action and action arguments.
    """
    f = submission.cleaned_form_url
    f.query.remove("_of_action")
    f.query.remove("_of_action_params")
    _query = {
        "_of_action": action,
    }
    if action_params:
        _query["_of_action_params"] = json.dumps(action_params)

    return f.add(_query).url
