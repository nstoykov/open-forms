import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from openforms.config.models import GlobalConfiguration

from ..constants import SubmissionValueVariableSources


class SubmissionStep(models.Model):
    """
    Submission data.

    TODO: This model (and therefore API) allows for the same form step to be
    submitted multiple times. Can be useful for retrieving historical data or
    changes made during filling out the form... but...
    """

    uuid = models.UUIDField(_("UUID"), unique=True, default=uuid.uuid4)
    submission = models.ForeignKey("submissions.Submission", on_delete=models.CASCADE)
    form_step = models.ForeignKey("forms.FormStep", on_delete=models.CASCADE)
    _data = models.JSONField(_("data"), blank=True, null=True)
    created_on = models.DateTimeField(_("created on"), auto_now_add=True)
    modified = models.DateTimeField(_("modified on"), auto_now=True)

    # can be modified by logic evaluations/checks
    _can_submit = True
    _is_applicable = True

    class Meta:
        verbose_name = _("Submission step")
        verbose_name_plural = _("Submission steps")
        unique_together = (("submission", "form_step"),)

    def __str__(self):
        return f"SubmissionStep {self.pk}: Submission {self.submission_id} submitted on {self.created_on}"

    @property
    def completed(self) -> bool:
        # TODO: should check that all the data for the form definition is present?
        # and validates?
        # For now - if it's been saved, we assume that was because it was completed
        return bool(self.pk and self.data is not None)

    @property
    def can_submit(self) -> bool:
        return self._can_submit

    @property
    def is_applicable(self) -> bool:
        return self._is_applicable

    def reset(self):
        self._data = None
        self.save()

    @property
    def data(self) -> dict:
        config = GlobalConfiguration.get_solo()
        if config.enable_form_variables:
            values_state = self.submission.load_submission_value_variables_state()
            variables_in_step = values_state.get_variables_in_submission_step(self)
            return {
                variable.key: variable.value
                for variable in variables_in_step
                if variable.value != ""
                or variable.source
                == SubmissionValueVariableSources.sensitive_data_cleaner
            }
        else:
            return self._data

    @data.setter
    def data(self, data):
        config = GlobalConfiguration.get_solo()
        if config.enable_form_variables:
            self.submission.update_submission_value_variables_state(data=data)
        else:
            self._data = data
