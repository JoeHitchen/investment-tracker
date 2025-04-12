from typing import TypeVar

Obj = TypeVar('Obj')


def exists(obj: Obj | None) -> Obj:
    assert obj
    return obj

