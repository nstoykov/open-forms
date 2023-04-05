from unittest.mock import patch

from django.urls import reverse

from rest_framework import serializers, status
from rest_framework.test import APITestCase

from openforms.accounts.tests.factories import SuperUserFactory
from openforms.payments.base import BasePlugin as PaymentBasePlugin
from openforms.payments.registry import Registry as PaymentRegistry
from openforms.registrations.base import BasePlugin as RegistrationBasePlugin
from openforms.registrations.registry import Registry as RegistrationRegistry
from openforms.registrations.tests.utils import patch_registry

from ..models import Form
from .factories import FormFactory


class EmailOptionsSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class RegistrationPlugin(RegistrationBasePlugin):
    configuration_options = EmailOptionsSerializer

    def register_submission(self, submission, options):
        pass

    def get_reference_from_result(self, result: dict) -> None:
        pass


class PaymentPlugin(PaymentBasePlugin):
    configuration_options = EmailOptionsSerializer


class FormPluginOptionTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = SuperUserFactory()
        self.client.force_authenticate(user=self.user)

    def test_registration_backend_options(self):
        form = FormFactory.create()

        url = reverse("api:form-detail", kwargs={"uuid_or_slug": form.uuid})
        model_field = Form._meta.get_field("registration_backend")

        register = RegistrationRegistry()
        register("test")(RegistrationPlugin)

        patcher = patch(
            "openforms.forms.api.serializers.form.registration_register", new=register
        )
        with patcher, patch_registry(model_field, register):
            with self.subTest("blank"):
                response = self.client.patch(
                    url,
                    data={
                        "registration_backend": "",
                        "registration_backend_options": None,
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                form.refresh_from_db()
                self.assertEqual(form.registration_backend, "")
                self.assertEqual(form.registration_backend_options, None)

            with self.subTest("valid"):
                response = self.client.patch(
                    url,
                    data={
                        "registration_backend": "test",
                        "registration_backend_options": {"email": "foo@bar.baz"},
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                form.refresh_from_db()
                self.assertEqual(form.registration_backend, "test")
                self.assertEqual(
                    form.registration_backend_options, {"email": "foo@bar.baz"}
                )

            with self.subTest("invalid"):
                response = self.client.patch(
                    url,
                    data={
                        "registration_backend": "test",
                        "registration_backend_options": {"email": "not_email_address"},
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

                json = response.json()
                self.assertEqual(json["code"], "invalid")
                self.assertEqual(
                    json["invalidParams"][0]["name"], "registrationBackendOptions.email"
                )

    def test_payment_backend_options(self):
        form = FormFactory.create()

        url = reverse("api:form-detail", kwargs={"uuid_or_slug": form.uuid})
        model_field = Form._meta.get_field("payment_backend")

        register = PaymentRegistry()
        register("test")(PaymentPlugin)

        patcher = patch(
            "openforms.forms.api.serializers.form.payment_register", new=register
        )
        with patcher, patch_registry(model_field, register):
            with self.subTest("blank"):
                response = self.client.patch(
                    url,
                    data={
                        "payment_backend": "",
                        "payment_backend_options": None,
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                form.refresh_from_db()
                self.assertEqual(form.payment_backend, "")
                self.assertEqual(form.payment_backend_options, None)

            with self.subTest("valid"):
                response = self.client.patch(
                    url,
                    data={
                        "payment_backend": "test",
                        "payment_backend_options": {"email": "foo@bar.baz"},
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                form.refresh_from_db()
                self.assertEqual(form.payment_backend, "test")
                self.assertEqual(form.payment_backend_options, {"email": "foo@bar.baz"})

            with self.subTest("invalid"):
                response = self.client.patch(
                    url,
                    data={
                        "payment_backend": "test",
                        "payment_backend_options": {"email": "not_email_address"},
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

                json = response.json()
                self.assertEqual(json["code"], "invalid")
                self.assertEqual(
                    json["invalidParams"][0]["name"], "paymentBackendOptions.email"
                )

    def test_overwrite_only_registration_email_subject_templates(self):
        form = FormFactory.create(
            registration_backend="email",
            registration_backend_options={"to_emails": ["test@test.nl"]},
        )

        url = reverse("api:form-detail", kwargs={"uuid_or_slug": form.uuid})

        response = self.client.patch(
            url,
            data={
                "registration_email_subject": "Custom subject",
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["registrationEmailSubject"], "Custom subject")
        self.assertEqual(
            data["registrationEmailPaymentSubject"],
            form.registration_email_payment_subject,
        )
        self.assertEqual(
            data["registrationEmailContentHtml"],
            form.registration_email_content_html,
        )
        self.assertEqual(
            data["registrationEmailContentText"],
            form.registration_email_content_text,
        )

    def test_overwrite_both_registration_email_html_and_text_templates(self):
        form = FormFactory.create(
            registration_backend="email",
            registration_backend_options={"to_emails": ["test@test.nl"]},
        )

        url = reverse("api:form-detail", kwargs={"uuid_or_slug": form.uuid})

        response = self.client.patch(
            url,
            data={
                "registration_email_content_html": "Custom HTML template {% payment_information %}",
                "registration_email_content_text": "Custom text template {% payment_information %}",
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            data["registrationEmailSubject"], form.registration_email_subject
        )
        self.assertEqual(
            data["registrationEmailPaymentSubject"],
            form.registration_email_payment_subject,
        )
        self.assertEqual(
            data["registrationEmailContentHtml"],
            "Custom HTML template {% payment_information %}",
        )
        self.assertEqual(
            data["registrationEmailContentText"],
            "Custom text template {% payment_information %}",
        )

    def test_cannot_overwrite_only_registration_email_html_template(self):
        form = FormFactory.create(
            registration_backend="email",
            registration_backend_options={"to_emails": ["test@test.nl"]},
        )

        url = reverse("api:form-detail", kwargs={"uuid_or_slug": form.uuid})

        response = self.client.patch(
            url,
            data={
                "registration_email_content_html": "Custom HTML template {% payment_information %}",
            },
        )

        self.assertEqual(response.status_code, 400)

        data = response.json()

        self.assertEqual(
            data["invalidParams"][0]["reason"],
            "The fields registration_email_content_html, registration_email_content_text must all have a "
            "non-empty value as soon as one of them does.",
        )
