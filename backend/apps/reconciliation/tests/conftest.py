import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture
def seed(db):
    call_command("seed_demo")


def make_client(slug):
    client = APIClient()
    if slug is not None:
        client.credentials(HTTP_X_ORGANIZATION=slug)
    return client


@pytest.fixture
def north_client(seed):
    return make_client("northwind")


@pytest.fixture
def blue_client(seed):
    return make_client("bluebird")


def upload(client, text, filename="stmt.csv"):
    data = text.encode("utf-8-sig") if isinstance(text, str) else text
    return client.post(
        "/api/imports/",
        {"file": SimpleUploadedFile(filename, data, content_type="text/csv")},
        format="multipart",
    )
