from typing import List

from mipengine import config
from mipengine.common.node_tasks_DTOs import TableInfo
from mipengine.common.validators import validate_sql_params
from mipengine.node.monetdb_interface.common_actions import get_table_names
from mipengine.node.monetdb_interface.common_actions import (
    convert_schema_to_sql_query_format,
)
from mipengine.node.monetdb_interface.monet_db_connection import MonetDB


def get_remote_table_names(context_id: str) -> List[str]:
    return get_table_names("remote", context_id)


@validate_sql_params
def create_remote_table(table_info: TableInfo, db_socket_address: str):
    columns_schema = convert_schema_to_sql_query_format(table_info.schema)
    MonetDB().execute(
        f"""
        CREATE REMOTE TABLE {table_info.name}
        ( {columns_schema}) ON 'mapi:monetdb://{db_socket_address}/{config.monetdb.database}'
        WITH USER 'monetdb' PASSWORD 'monetdb'
        """
    )
