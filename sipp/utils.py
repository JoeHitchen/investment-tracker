from typing import TypedDict, TypeVar

Obj = TypeVar('Obj')


class Kwargs(TypedDict):
    pass


def exists(obj: Obj | None) -> Obj:
    assert obj
    return obj

