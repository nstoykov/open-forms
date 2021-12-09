from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from openforms.accounts.tests.factories import UserFactory

from ..models import FormDefinition
from .factories import FormDefinitionFactory, FormStepFactory


class FormDefinitionsAPITests(APITestCase):
    def setUp(self):
        # TODO: Replace with API-token
        User = get_user_model()
        user = User.objects.create_user(
            username="john", password="secret", email="john@example.com"
        )

        # TODO: Axes requires HttpRequest, should we have that in the API at all?
        assert self.client.login(
            request=HttpRequest(), username=user.username, password="secret"
        )

    def test_list(self):
        FormDefinitionFactory.create_batch(2)

        url = reverse("api:formdefinition-list")
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_user_cant_update(self):
        definition = FormDefinitionFactory.create(
            name="test form definition",
            slug="test-form-definition",
            configuration={
                "display": "form",
                "components": [{"label": "Existing field"}],
            },
        )

        url = reverse("api:formdefinition-detail", kwargs={"uuid": definition.uuid})
        response = self.client.patch(
            url,
            data={
                "name": "Updated name",
                "slug": "updated-slug",
                "configuration": {
                    "display": "form",
                    "components": [{"label": "Existing field"}, {"label": "New field"}],
                },
            },
        )

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_non_staff_user_cant_create(self):
        url = reverse("api:formdefinition-list")
        response = self.client.post(
            url,
            data={
                "name": "Name",
                "slug": "a-slug",
                "configuration": {
                    "display": "form",
                    "components": [{"label": "New field"}],
                },
            },
        )

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_non_staff_user_cant_delete(self):
        definition = FormDefinitionFactory.create(
            name="test form definition",
            slug="test-form-definition",
            configuration={
                "display": "form",
                "components": [{"label": "Existing field"}],
            },
        )

        url = reverse("api:formdefinition-detail", kwargs={"uuid": definition.uuid})
        response = self.client.delete(url)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_update(self):
        staff_user = UserFactory.create(is_staff=True)
        self.client.force_login(staff_user)

        definition = FormDefinitionFactory.create(
            name="test form definition",
            slug="test-form-definition",
            login_required=False,
            configuration={
                "display": "form",
                "components": [{"label": "Existing field"}],
            },
        )

        url = reverse("api:formdefinition-detail", kwargs={"uuid": definition.uuid})
        response = self.client.patch(
            url,
            data={
                "name": "Updated name",
                "slug": "updated-slug",
                "configuration": {
                    "display": "form",
                    "components": [{"label": "Existing field"}, {"label": "New field"}],
                },
                "login_required": True,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        definition.refresh_from_db()

        self.assertEqual("Updated name", definition.name)
        self.assertEqual("updated-slug", definition.slug)
        self.assertEqual(True, definition.login_required)
        self.assertIn({"label": "New field"}, definition.configuration["components"])

    def test_create(self):
        staff_user = UserFactory.create(is_staff=True)
        self.client.force_login(staff_user)

        url = reverse("api:formdefinition-list")
        response = self.client.post(
            url,
            data={
                "name": "Name",
                "slug": "a-slug",
                "configuration": {
                    "display": "form",
                    "components": [{"label": "New field"}],
                },
            },
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        definition = FormDefinition.objects.get()

        self.assertEqual("Name", definition.name)
        self.assertEqual("a-slug", definition.slug)
        self.assertEqual(
            [{"label": "New field"}], definition.configuration["components"]
        )

    def test_create_no_camelcase_snakecase_conversion(self):
        staff_user = UserFactory.create(is_staff=True)
        self.client.force_login(staff_user)

        url = reverse("api:formdefinition-list")
        response = self.client.post(
            url,
            data={
                "name": "Name",
                "slug": "a-slug",
                "configuration": {
                    "someCamelCase": "field",
                },
            },
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        config = FormDefinition.objects.get().configuration
        self.assertIn("someCamelCase", config)
        self.assertNotIn("some_amel_case", config)

    def test_delete(self):
        staff_user = UserFactory.create(is_staff=True)
        self.client.force_login(staff_user)

        definition = FormDefinitionFactory.create(
            name="test form definition",
            slug="test-form-definition",
            configuration={
                "display": "form",
                "components": [{"label": "Existing field"}],
            },
        )

        url = reverse("api:formdefinition-detail", kwargs={"uuid": definition.uuid})
        response = self.client.delete(url)

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(0, FormDefinition.objects.all().count())

    def test_used_in_forms_serializer_field(self):
        form_step = FormStepFactory.create()
        url = reverse(
            "api:formdefinition-detail", args=(form_step.form_definition.uuid,)
        )
        form_url = reverse("api:form-detail", args=(form_step.form.uuid,))

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(len(response_data["usedIn"]), 1)
        self.assertEqual(
            response_data["usedIn"][0]["url"], f"http://testserver{form_url}"
        )
