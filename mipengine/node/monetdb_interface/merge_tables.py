from typing import List

import pymonetdb

from mipengine.common.node_exceptions import IncompatibleSchemasMergeException
from mipengine.common.node_exceptions import IncompatibleTableTypes
from mipengine.common.node_exceptions import TableCannotBeFound
from mipengine.common.validate_identifier_names import validate_identifier_names
from mipengine.node.monetdb_interface import common_action
from mipengine.node.monetdb_interface.common_action import connection
from mipengine.node.monetdb_interface.common_action import convert_schema_to_sql_query_format
from mipengine.node.monetdb_interface.common_action import cursor
from mipengine.common.node_tasks_DTOs import TableInfo


def get_merge_tables_names(context_id: str) -> List[str]:
    return common_action.get_tables_names("merge", context_id)


@validate_identifier_names
def create_merge_table(table_info: TableInfo):
    columns_schema = convert_schema_to_sql_query_format(table_info.schema)
    cursor.execute(f"CREATE MERGE TABLE {table_info.name} ( {columns_schema} )")


@validate_identifier_names
def get_non_existing_tables(table_names: List[str]) -> List[str]:
    names_clause = str(table_names)[1:-1]
    cursor.execute(f"SELECT name FROM tables WHERE name IN({names_clause})")
    existing_table_names = [table[0] for table in cursor]
    return [name for name in table_names if name not in existing_table_names]


@validate_identifier_names
def add_to_merge_table(merge_table_name: str, tables_names: List[str]):
    non_existing_tables = get_non_existing_tables(tables_names)
    table_infos = [TableInfo(name, common_action.get_table_schema(name)) for name in tables_names]

    try:
        for name in tables_names:
            cursor.execute(f"ALTER TABLE {merge_table_name} ADD TABLE {name.lower()}")

    except pymonetdb.exceptions.OperationalError as exc:
        if str(exc).startswith('3F000'):
            connection.rollback()
            raise IncompatibleSchemasMergeException(table_infos)
        elif str(exc).startswith('42S02'):
            connection.rollback()
            raise TableCannotBeFound(non_existing_tables)
        else:
            connection.rollback()
            raise exc
    connection.commit()


@validate_identifier_names
def validate_tables_can_be_merged(tables_names: List[str]):
    table_names = ','.join(f"'{table}'" for table in tables_names)

    cursor.execute(
        f"""
        SELECT DISTINCT(type)
        FROM tables 
        WHERE
        system = false
        AND
        name in ({table_names})""")

    tables_types = cursor.fetchall()
    if len(tables_types) != 1:
        raise IncompatibleTableTypes(tables_types)
