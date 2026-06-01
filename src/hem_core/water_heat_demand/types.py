from typing import TypedDict


class Event(TypedDict):
    start: float
    duration: float
    temperature: float
    type: str
    name: str
