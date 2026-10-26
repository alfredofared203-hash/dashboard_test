import re


TASK_ID_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SESSION_ID_PATTERN = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)


def is_valid_task_id(value: str) -> bool:
    return TASK_ID_PATTERN.fullmatch(value) is not None


def is_valid_session_id(value: str) -> bool:
    return SESSION_ID_PATTERN.fullmatch(value) is not None
