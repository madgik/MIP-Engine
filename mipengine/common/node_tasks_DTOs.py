from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class ColumnInfo:
    name: str
    data_type: str

    def __post_init__(self):
        allowed_types = {"int", "text", "real"}
        self.data_type = str.lower(self.data_type)
        if self.data_type not in allowed_types:
            raise TypeError(
                f"Column can have one of the following types: {allowed_types}"
            )


@dataclass_json
@dataclass
class TableSchema:
    columns: List[ColumnInfo]


@dataclass_json
@dataclass
class TableInfo:
    name: str
    schema: TableSchema


@dataclass_json
@dataclass
class TableView:
    datasets: List[str]
    columns: List[str]
    filter: Dict


@dataclass_json
@dataclass
class TableData:
    schema: TableSchema
    data: List[List[Union[str, int, float, bool]]]


@dataclass_json
@dataclass
class UDFArgument:
    type: str
    value: Any

    def __post_init__(self):
        allowed_types = {"table", "literal"}
        if self.type not in allowed_types:
            raise TypeError(
                f"UDFArgument type  can have one of the following types: {allowed_types}"
            )
