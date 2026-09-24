import json
import os

os.environ["TABLE_NAME"] = "test-notes"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
import pytest
from moto import mock_aws

from src import lambda_function


@pytest.fixture()
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="test-notes",
            KeySchema=[{"AttributeName": "noteId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "noteId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        lambda_function._table = None  # reset cached table
        yield


def ev(method, resource="/notes", note_id=None, body=None):
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": {"noteId": note_id} if note_id else None,
        "body": json.dumps(body) if body is not None else None,
    }


def test_create_and_get_note(table):
    r = lambda_function.lambda_handler(ev("POST", body={"title": "hello"}), None)
    assert r["statusCode"] == 201
    note_id = json.loads(r["body"])["noteId"]

    r = lambda_function.lambda_handler(ev("GET", note_id=note_id), None)
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["title"] == "hello"


def test_get_missing_note_404(table):
    r = lambda_function.lambda_handler(ev("GET", note_id="nope"), None)
    assert r["statusCode"] == 404


def test_create_without_title_400(table):
    r = lambda_function.lambda_handler(ev("POST", body={"content": "x"}), None)
    assert r["statusCode"] == 400


def test_invalid_json_400(table):
    e = ev("POST")
    e["body"] = "{not json"
    r = lambda_function.lambda_handler(e, None)
    assert r["statusCode"] == 400


def test_update_and_delete(table):
    note_id = json.loads(lambda_function.lambda_handler(
        ev("POST", body={"title": "t"}), None)["body"])["noteId"]

    r = lambda_function.lambda_handler(ev("PUT", note_id=note_id, body={"title": "t2"}), None)
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["title"] == "t2"

    r = lambda_function.lambda_handler(ev("DELETE", note_id=note_id), None)
    assert r["statusCode"] == 204

    r = lambda_function.lambda_handler(ev("DELETE", note_id=note_id), None)
    assert r["statusCode"] == 404
