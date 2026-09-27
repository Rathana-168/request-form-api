from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum_cls: type[StrEnum], length: int = 30) -> Enum:
    """Store a StrEnum as VARCHAR (not a PostgreSQL ENUM type).

    Adding a new value later needs no migration and no ALTER TYPE.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )
