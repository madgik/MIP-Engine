from typing import List

from mipengine.common.node_tasks_DTOs import TableInfo
from mipengine.common.validators import validate_sql_params
from mipengine.node.monetdb_interface import common_actions
from mipengine.node.monetdb_interface.common_actions import (
    convert_schema_to_sql_query_format,
)
from mipengine.node.monetdb_interface.monet_db_connection import MonetDB


def get_table_names(context_id: str) -> List[str]:
    return common_actions.get_table_names("normal", context_id)


@validate_sql_params
def create_table(table_info: TableInfo):
    columns_schema = convert_schema_to_sql_query_format(table_info.schema)
    MonetDB().execute(f"CREATE TABLE {table_info.name} ( {columns_schema} )")
