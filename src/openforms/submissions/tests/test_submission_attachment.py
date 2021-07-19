import os

from django.core.files import File
from django.test import TestCase, override_settings

from PIL import Image, UnidentifiedImageError
from privates.test import temp_private_root

from openforms.forms.tests.factories import FormStepFactory
from openforms.submissions.attachments import (
    append_file_num_postfix,
    attach_uploads_to_submission_step,
    clean_mime_type,
    cleanup_submission_temporary_uploaded_files,
    resize_attachment,
    resolve_uploads_from_data,
)
from openforms.submissions.models import SubmissionFileAttachment
from openforms.submissions.tests.factories import (
    SubmissionFileAttachmentFactory,
    SubmissionStepFactory,
    TemporaryFileUploadFactory,
)


@temp_private_root()
class SubmissionAttachmentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_image_path = os.path.join(
            os.path.dirname(__file__), "files", "image-256x256.png"
        )

    # TODO private storage
    def test_resolve_uploads_from_formio_data(self):
        upload = TemporaryFileUploadFactory.create()
        data = {
            "my_normal_key": "foo",
            "my_file": [
                {
                    "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                    "data": {
                        "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                        "form": "",
                        "name": "my-image.jpg",
                        "size": 46114,
                        "baseUrl": "http://server",
                        "project": "",
                    },
                    "name": "my-image-12305610-2da4-4694-a341-ccb919c3d543.jpg",
                    "size": 46114,
                    "type": "image/jpg",
                    "storage": "url",
                    "originalName": "my-image.jpg",
                }
            ],
        }
        components = [
            {"key": "my_normal_key", "type": "text"},
            {"key": "my_file", "type": "file"},
        ]
        actual = resolve_uploads_from_data(components, data)
        self.assertEqual(actual, {"my_file": (components[1], [upload])})

    def test_attach_uploads_to_submission_step(self):
        upload = TemporaryFileUploadFactory.create(file_name="my-image.jpg")
        data = {
            "my_normal_key": "foo",
            "my_file": [
                {
                    "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                    "data": {
                        "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                        "form": "",
                        "name": "my-image.jpg",
                        "size": 46114,
                        "baseUrl": "http://server",
                        "project": "",
                    },
                    "name": "my-image-12305610-2da4-4694-a341-ccb919c3d543.jpg",
                    "size": 46114,
                    "type": "image/jpg",
                    "storage": "url",
                    "originalName": "my-image.jpg",
                }
            ],
        }
        components = [
            {"key": "my_normal_key", "type": "text"},
            {"key": "my_file", "type": "file", "file": {"name": "my-filename.txt"}},
        ]
        form_step = FormStepFactory.create(
            form_definition__configuration={"components": components}
        )
        submission_step = SubmissionStepFactory.create(
            form_step=form_step, submission__form=form_step.form, data=data
        )

        # test attaching the file
        result = attach_uploads_to_submission_step(submission_step)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], True)  # created new
        self.assertEqual(SubmissionFileAttachment.objects.count(), 1)

        attachment = submission_step.attachments.get()
        self.assertEqual(attachment.form_key, "my_file")
        self.assertEqual(attachment.file_name, "my-filename.txt")
        self.assertEqual(attachment.original_name, "my-image.jpg")
        self.assertEqual(attachment.content.read(), b"content")
        self.assertEqual(attachment.content_type, upload.content_type)
        self.assertEqual(attachment.temporary_file, upload)

        # test attaching again is idempotent
        result = attach_uploads_to_submission_step(submission_step)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], False)  # not created
        self.assertEqual(SubmissionFileAttachment.objects.count(), 1)

        # test cleanup
        cleanup_submission_temporary_uploaded_files(submission_step.submission)
        attachment.refresh_from_db()
        self.assertEqual(attachment.temporary_file, None)
        # verify the new FileField has its own content
        self.assertEqual(attachment.content.read(), b"content")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_attach_uploads_to_submission_step_resizes_image(self):
        upload = TemporaryFileUploadFactory.create(
            file_name="my-image.png", content=File(open(self.test_image_path, "rb"))
        )
        data = {
            "my_normal_key": "foo",
            "my_file": [
                {
                    "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                    "data": {
                        "url": f"http://server/api/v1/submissions/files/{upload.uuid}",
                        "form": "",
                        "name": "my-image.png",
                        "size": 46114,
                        "baseUrl": "http://server",
                        "project": "",
                    },
                    "name": "my-image-12305610-2da4-4694-a341-ccb919c3d543.png",
                    "size": 46114,
                    "type": "image/png",
                    "storage": "url",
                    "originalName": "my-image.png",
                }
            ],
        }
        components = [
            {"key": "my_normal_key", "type": "text"},
            {
                "key": "my_file",
                "type": "file",
                "image": {"resize": {"apply": True, "width": 100, "height": 100}},
            },
        ]
        form_step = FormStepFactory.create(
            form_definition__configuration={"components": components}
        )
        submission_step = SubmissionStepFactory.create(
            form_step=form_step, submission__form=form_step.form, data=data
        )

        # test attaching the file
        result = attach_uploads_to_submission_step(submission_step)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], True)  # created new
        self.assertEqual(SubmissionFileAttachment.objects.count(), 1)

        attachment = submission_step.attachments.get()
        self.assertEqual(attachment.form_key, "my_file")
        self.assertEqual(attachment.original_name, "my-image.png")
        self.assertImageSize(attachment.content, 100, 100, "png")

        attachment.delete()

    def assertImageSize(self, file, width, height, format):
        image = Image.open(file, formats=(format,))
        self.assertEqual(image.width, width)
        self.assertEqual(image.height, height)

    def test_assertImageSize(self):
        self.assertImageSize(self.test_image_path, 256, 256, "png")

        with self.assertRaises(AssertionError):
            self.assertImageSize(self.test_image_path, 1000, 256, "png")
        with self.assertRaises(AssertionError):
            self.assertImageSize(self.test_image_path, 256, 1000, "png")
        with self.assertRaises(UnidentifiedImageError):
            self.assertImageSize(self.test_image_path, 256, 256, "jpeg")

    def test_resize_attachment_helper(self):
        with open(self.test_image_path, "rb") as f:
            data = f.read()

        attachment = SubmissionFileAttachmentFactory.create(
            content__name="my-image.png", content__data=data
        )
        # too small to resize
        res = resize_attachment(attachment, (1024, 1024))
        self.assertEqual(res, False)

        # same size as required
        res = resize_attachment(attachment, (256, 256))
        self.assertEqual(res, False)

        # good, actually resize
        res = resize_attachment(attachment, (200, 200))
        self.assertEqual(res, True)
        self.assertImageSize(attachment.content, 200, 200, "png")

        # but not resize again to same size
        res = resize_attachment(attachment, (200, 200))
        self.assertEqual(res, False)

        # don't crash on corrupt image
        attachment_bad = SubmissionFileAttachmentFactory.create(
            content__name="my-image.png", content__data=b"broken"
        )
        res = resize_attachment(attachment_bad, (1024, 1024))
        self.assertEqual(res, False)

        # don't crash on missing file
        attachment_bad = SubmissionFileAttachmentFactory.create()
        attachment_bad.content.delete()
        res = resize_attachment(attachment_bad, (1024, 1024))
        self.assertEqual(res, False)

    def test_append_file_num_postfix_helper(self):
        actual = append_file_num_postfix("base.txt", 1, 1)
        self.assertEqual("base.txt", actual)

        actual = append_file_num_postfix("base.txt", 1, 5)
        self.assertEqual("base-1.txt", actual)

        actual = append_file_num_postfix("base.txt", 2, 5)
        self.assertEqual("base-2.txt", actual)

        actual = append_file_num_postfix("base.txt", 1, 20)
        self.assertEqual("base-01.txt", actual)

        actual = append_file_num_postfix("base.txt", 11, 20)
        self.assertEqual("base-11.txt", actual)

    def test_clean_mime_type_helper(self):
        actual = clean_mime_type("text/plain")
        self.assertEqual("text/plain", actual)

        actual = clean_mime_type("text/plain/xxx")
        self.assertEqual("text/plain", actual)

        actual = clean_mime_type("text/plain-xxx")
        self.assertEqual("text/plain-xxx", actual)

        actual = clean_mime_type("text/plain-x.x.x")
        self.assertEqual("text/plain-x.x.x", actual)

        actual = clean_mime_type("xxxx")
        self.assertEqual("application/octet-stream", actual)

        actual = clean_mime_type("")
        self.assertEqual("application/octet-stream", actual)
