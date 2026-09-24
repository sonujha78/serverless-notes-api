import json
import os
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ["TABLE_NAME"]

_table = None

def get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table

def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }

def lambda_handler(event, context):
    method = event.get("httpMethod")
    resource = event.get("resource", "")
    path_params = event.get("pathParameters") or {}
    note_id = path_params.get("noteId")
    table = get_table()

    try:
        if method == "GET" and note_id is None:
            return respond(200, {"notes": table.scan().get("Items", [])})

        if method == "POST" and note_id is None:
            try:
                payload = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return respond(400, {"error": "Invalid JSON body"})
            if not payload.get("title"):
                return respond(400, {"error": "'title' is required"})
            new_id = str(uuid.uuid4())
            table.put_item(Item={"noteId": new_id, "title": payload["title"],
                                 "content": payload.get("content", "")})
            return respond(201, {"noteId": new_id})

        if note_id is None:
            return respond(400, {"error": "noteId path parameter missing"})

        if method == "GET":
            item = table.get_item(Key={"noteId": note_id}).get("Item")
            if not item:
                return respond(404, {"error": "note not found"})
            return respond(200, item)

        if method == "PUT":
            try:
                payload = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return respond(400, {"error": "Invalid JSON body"})
            if not payload:
                return respond(400, {"error": "empty update body"})
            expr, names, values = "SET ", {}, {}
            for i, (k, v) in enumerate(payload.items()):
                names[f"#a{i}"] = k
                values[f":v{i}"] = v
                expr += f"#a{i} = :v{i}," if i < len(payload) - 1 else f"#a{i} = :v{i}"
            try:
                res = table.update_item(
                    Key={"noteId": note_id},
                    UpdateExpression=expr,
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues=values,
                    ReturnValues="ALL_NEW",
                    ConditionExpression="attribute_exists(noteId)",
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return respond(404, {"error": "note not found"})
                raise
            return respond(200, res["Attributes"])

        if method == "DELETE":
            try:
                table.delete_item(Key={"noteId": note_id},
                                  ConditionExpression="attribute_exists(noteId)")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return respond(404, {"error": "note not found"})
                raise
            return respond(204, "")

        return respond(400, {"error": f"unsupported route: {method} {resource}"})

    except ClientError as e:
        return respond(500, {"error": "internal server error",
                             "detail": e.response["Error"]["Message"]})
