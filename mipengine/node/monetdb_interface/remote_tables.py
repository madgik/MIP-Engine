from typing import List

from mipengine.common.node_tasks_DTOs import TableInfo
from mipengine.common.sql_injection_guard import sql_injection_guard
from mipengine.node.monetdb_interface.common_actions import get_table_names
from mipengine.node.monetdb_interface.common_actions import (
    convert_schema_to_sql_query_format,
)
from mipengine.node.monetdb_interface.monet_db_connection import MonetDB


def get_remote_table_names(context_id: str) -> List[str]:
    return get_table_names("remote", context_id)


@sql_injection_guard
def create_remote_table(table_info: TableInfo, db_location: str, db_name: str):
    columns_schema = convert_schema_to_sql_query_format(table_info.schema)
    MonetDB().execute(
        f"""
        CREATE REMOTE TABLE {table_info.name}
        ( {columns_schema}) ON 'mapi:monetdb://{db_location}/{db_name}'
        WITH USER 'monetdb' PASSWORD 'monetdb'
        """
    )
