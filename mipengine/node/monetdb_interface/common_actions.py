from typing import List
from typing import Union

from mipengine import config
from mipengine.common.node_tasks_DTOs import ColumnInfo
from mipengine.common.node_exceptions import TablesNotFound
from mipengine.common.node_tasks_DTOs import TableSchema
from mipengine.common.validators import validate_sql_params
from mipengine.node.monetdb_interface.monet_db_connection import MonetDB

MONETDB_VARCHAR_SIZE = 50

# TODO Add SQLAlchemy if possible
# TODO We need to add the PRIVATE/OPEN table logic


def create_table_name(
    table_type: str, command_id: str, context_id: str, node_id: str
) -> str:
    """
    Creates a table name with the format <tableType>_<commandId>_<contextId>_<nodeId>
    """
    if table_type not in {"table", "view", "merge"}:
        raise TypeError(f"Table type is not acceptable: {table_type} .")
    if node_id not in {"global", config.node.identifier}:
        raise TypeError(f"Node Identifier is not acceptable: {node_id}.")

    return f"{table_type}_{command_id}_{context_id}_{node_id}"


def convert_schema_to_sql_query_format(schema: TableSchema) -> str:
    """
    Converts a table's schema to a sql query.

    Parameters
    ----------
    schema : TableSchema
        The schema of a table

    Returns
    ------
    str
        The schema in a sql query formatted string
    """
    return ", ".join(
        f"{column.name} {_convert_mip2monetdb_column_type(column.data_type)}"
        for column in schema.columns
    )


@validate_sql_params
def get_table_schema(table_name: str) -> TableSchema:
    """
    Retrieves a schema for a specific table name  from the monetdb.

    Parameters
    ----------
    table_name : str
        The name of the table

    Returns
    ------
    TableSchema
        A schema which is TableSchema object.
    """
    schema = MonetDB().execute_with_result(
        f"""
        SELECT columns.name, columns.type
        FROM columns
        RIGHT JOIN tables
        ON tables.id = columns.table_id
        WHERE
        tables.name = '{table_name}'
        AND
        tables.system=false
        """
    )

    if not schema:
        raise TablesNotFound([table_name])
    return TableSchema(
        [
            ColumnInfo(name, _convert_monet2mip_column_type(table_type))
            for name, table_type in schema
        ]
    )


@validate_sql_params
def get_table_names(table_type: str, context_id: str) -> List[str]:
    """
    Retrieves a list of table names, which contain the context_id from the monetdb.

    Parameters
    ----------
    table_type : str
        The type of the table
    context_id : str
        The id of the experiment

    Returns
    ------
    List[str]
        A list of table names.
    """
    table_names = MonetDB().execute_with_result(
        f"""
        SELECT name FROM tables
        WHERE
         type = {str(_convert_mip2monet_table_type(table_type))} AND
        name LIKE '%{context_id.lower()}%' AND
        system = false"""
    )

    return [table[0] for table in table_names]


@validate_sql_params
def get_table_data(table_name: str) -> List[List[Union[str, int, float, bool]]]:
    """
    Retrieves the data of a table with specific name from the monetdb.

    Parameters
    ----------
    table_name : str
        The name of the table

    Returns
    ------
    List[List[Union[str, int, float, bool]]
        The data of the table.
    """

    data = MonetDB().execute_with_result(
        f"""
        SELECT {table_name}.*
        FROM {table_name}
        INNER JOIN tables ON tables.name = '{table_name}'
        WHERE tables.system=false
        """
    )

    return data


def clean_up(context_id: str):
    """
    Deletes all tables of any type with name that contain a specific
    context_id from the DB.

    Parameters
    ----------
    context_id : str
        The id of the experiment
    """
    # TODO We also need to cleanup the udfs with the specific context_id
    for table_type in ("merge", "remote", "view", "normal"):
        _delete_table_by_type_and_context_id(table_type, context_id)


def _convert_monet2mip_table_type(monet_table_type: int) -> str:
    """
    Converts MonetDB's table types to MIP Engine's table types
    """
    type_mapping = {
        0: "normal",
        1: "view",
        3: "merge",
        5: "remote",
    }

    if monet_table_type not in type_mapping.keys():
        raise ValueError(
            f"Type {monet_table_type} cannot be converted to MIP Engine's table types."
        )

    return type_mapping.get(monet_table_type)


def _convert_mip2monet_table_type(table_type: str) -> int:
    """
    Converts MIP Engine's table types to MonetDB's table types
    """
    type_mapping = {
        "normal": 0,
        "view": 1,
        "merge": 3,
        "remote": 5,
    }

    if table_type not in type_mapping.keys():
        raise ValueError(
            f"Type {table_type} cannot be converted to monetdb table type."
        )

    return type_mapping.get(table_type)


def _convert_mip2monetdb_column_type(column_type: str) -> str:
    """
    Converts MIP Engine's int,real,text types to monetdb
    """
    type_mapping = {
        "int": "int",
        "real": "real",
        "text": f"varchar({MONETDB_VARCHAR_SIZE})",
    }

    if column_type not in type_mapping.keys():
        raise ValueError(
            f"Type {column_type} cannot be converted to monetdb column type."
        )

    return type_mapping.get(column_type)


def _convert_monet2mip_column_type(column_type: str) -> str:
    """
    Converts MonetDB's types to MIP's types
    """
    type_mapping = {
        "int": "int",
        "double": "real",
        "real": "real",
        "varchar": "text",
    }

    if column_type not in type_mapping.keys():
        raise ValueError(f"Type {column_type} cannot be converted to MIP's types.")

    return type_mapping.get(column_type)


@validate_sql_params
def _delete_table_by_type_and_context_id(table_type: str, context_id: str):
    """
    Deletes all tables of specific type with name that contain a specific context_id from the monetdb.

    Parameters
    ----------
    table_type : str
        The type of the table
    context_id : str
        The id of the experiment
    """
    table_names_and_types = MonetDB().execute_with_result(
        f"""
        SELECT name, type FROM tables
        WHERE name LIKE '%{context_id.lower()}%'
        AND tables.type = {str(_convert_mip2monet_table_type(table_type))}
        AND system = false
        """
    )
    for name, table_type in table_names_and_types:
        if table_type == _convert_mip2monet_table_type("view"):
            MonetDB().execute(f"DROP VIEW {name}")
        else:
            MonetDB().execute(f"DROP TABLE {name}")
