import uuid
from typing import Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema


class AttachmentId(uuid.UUID):
    """A UUID that marks 'this is an attachment'. Accepts an id, or an object with `id`
    (so read-schema output can be fed back into the create schema on update)."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler):
        def to_id(v: Any) -> AttachmentId:
            if isinstance(v, dict):
                v = v.get("id")
            elif hasattr(v, "id") and not isinstance(v, (str, uuid.UUID)):
                v = v.id
            return cls(str(v))

        return core_schema.no_info_plain_validator_function(
            to_id,
            serialization=core_schema.plain_serializer_function_ser_schema(str, when_used="json"),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler: GetJsonSchemaHandler):
        return {"type": "string", "format": "uuid"}


def collect_attachment_ids(value: Any) -> set[uuid.UUID]:
    """All AttachmentId values in validated data, at any depth."""
    if isinstance(value, AttachmentId):
        return {uuid.UUID(int=value.int)}
    if hasattr(value, "model_fields"):          # a Pydantic model
        value = dict(value)
    if isinstance(value, dict):
        value = value.values()
    if isinstance(value, (list, tuple, set)) or hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        out: set[uuid.UUID] = set()
        for v in value:
            out |= collect_attachment_ids(v)
        return out
    return set()