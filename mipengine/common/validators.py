import dataclasses
from functools import wraps
import re


def validate_sql_params(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        _validate_recursively(*args, **kwargs)
        return func(*args, **kwargs)

    return wrapper


def _validate_recursively(*args, **kwargs):
    all_args = list(args) + list(kwargs.values()) + list(kwargs.keys())
    for arg in all_args:
        if isinstance(arg, str):
            _validate_sql_param(arg)
        elif isinstance(arg, list):
            _validate_recursively(*arg)
        elif isinstance(arg, dict):
            _validate_recursively(**arg)
        elif dataclasses.is_dataclass(arg):
            _validate_recursively(dataclasses.asdict(arg))
        else:
            raise ValueError(f"Expected valid SQL parameter, got {arg}")


def _validate_sql_param(arg):
    if arg.isidentifier():
        return
    elif arg.isalnum():
        return
    elif _validate_socket_address(arg):
        return
    else:
        raise ValueError(f"Invalid SQL parameter {arg}")


def _validate_socket_address(arg):
    return re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}", arg) is not None
