from typing import List
from typing import Union

import pymonetdb

from mipengine.common.node_catalog import NodeCatalog
from mipengine.node.node import config
from mipengine.node.tasks.data_classes import ColumnInfo
from mipengine.node.tasks.data_classes import TableSchema
from mipengine.utils.verify_identifier_names import sql_injections_defender

MONETDB_VARCHAR_SIZE = 50

# TODO Add monetdb asyncio connection (aiopymonetdb)
node_catalog = NodeCatalog()
local_node = node_catalog.get_local_node_data(config.get("node", "identifier"))
monetdb_hostname = local_node.monetdbHostname
monetdb_port = local_node.monetdbPort
connection = pymonetdb.connect(username=config.get("monet_db", "username"),
                               port=monetdb_port,
                               password=config.get("monet_db", "password"),
                               hostname=monetdb_hostname,
                               database=config.get("monet_db", "database"))
cursor = connection.cursor()


def create_table_name(table_type: str, command_id: str, context_id: str, node_id: str) -> str:
    """
    Creates a table name with the format <table_type>_<context_id>_<node_id>_<uuid>
    """
    if table_type not in {"table", "view", "merge"}:
        raise TypeError(f"Table type is not acceptable: {table_type} .")
    if node_id not in {"global", config.get("node", "identifier")}:
        raise TypeError(f"Node Identifier is not acceptable: {node_id} .")

    return f"{table_type}_{command_id}_{context_id}_{node_id}"


# TODO Add SQLAlchemy if possible
# TODO We need to add the PRIVATE/OPEN table logic

def get_table_type_enumeration_value(table_type: str) -> int:
    """ Converts MIP Engine's table types to MonetDB's table types
     normal -> 0,
     view -> 1,
     merge -> 3,
     remote -> 5,
        """
    type_mapping = {
        "normal": 0,
        "view": 1,
        "merge": 3,
        "remote": 5,
    }

    if table_type not in type_mapping.keys():
        raise ValueError(f"Type {table_type} cannot be converted to monetdb table type.")

    return type_mapping.get(str(table_type).lower())


def convert_to_monetdb_column_type(column_type: str) -> str:
    """ Converts MIP Engine's int,float,text types to monetdb
    int -> integer
    float -> double
    text -> varchar(50s)
    bool -> boolean
    clob -> clob
    """
    type_mapping = {
        "int": "int",
        "float": "double",
        "text": f"varchar({MONETDB_VARCHAR_SIZE})",
        "bool": "bool",
        "clob": "clob",
    }

    if column_type not in type_mapping.keys():
        raise ValueError(f"Type {column_type} cannot be converted to monetdb column type.")

    return type_mapping.get(str(column_type).lower())


def convert_from_monetdb_column_type(column_type: str) -> str:
    """ Converts MonetDB's types to MIP Engine's types
    int ->  int
    double  -> float
    varchar(50)  -> text
    boolean -> bool
    clob -> clob
    """
    type_mapping = {
        "int": "int",
        "double": "float",
        "varchar": "text",
        "bool": "bool",
        "clob": "clob",
    }

    if column_type not in type_mapping.keys():
        raise ValueError(f"Type {column_type} cannot be converted to MIP Engine's types.")

    return type_mapping.get(str(column_type).lower())


@sql_injections_defender
def get_table_schema(table_type: str, table_name: str) -> TableSchema:
    """Retrieves a schema for a specific table type and table name  from the monetdb.

        Parameters
        ----------
        table_type : str
            The type of the table
        table_name : str
            The name of the table

        Returns
        ------
        TableSchema
            A schema which is TableSchema object.
    """
    cursor.execute(
        f"""
        SELECT columns.name, columns.type 
        FROM columns 
        RIGHT JOIN tables 
        ON tables.id = columns.table_id 
        WHERE 
        tables.type = {str(get_table_type_enumeration_value(table_type))} 
        AND 
        tables.name = '{table_name}' 
        AND 
        tables.system=false""")

    return TableSchema([ColumnInfo(table[0], convert_from_monetdb_column_type(table[1])) for table in cursor])


@sql_injections_defender
def get_tables_names(table_type: str, context_id: str) -> List[str]:
    """Retrieves a list of table names, which contain the context_id from the monetdb.

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
    cursor.execute(
        f"""
        SELECT name FROM tables 
        WHERE
         type = {str(get_table_type_enumeration_value(table_type))} AND
        name LIKE '%{context_id.lower()}%' AND 
        system = false""")

    return [table[0] for table in cursor]


def convert_schema_to_sql_query_format(schema: TableSchema) -> str:
    """Converts a table's schema to a sql query.

        Parameters
        ----------
        schema : TableSchema
            The schema of a table

        Returns
        ------
        str
            The schema in a sql query formatted string
    """
    return ', '.join(f"{column.name} {convert_to_monetdb_column_type(column.data_type)}" for column in schema.columns)


@sql_injections_defender
def get_table_data(table_type: str, table_name: str) -> List[List[Union[str, int, float, bool]]]:
    """Retrieves the data of a table with specific type and name  from the monetdb.

        Parameters
        ----------
        table_type : str
            The type of the table
        table_name : str
            The name of the table

        Returns
        ------
        List[List[Union[str, int, float, bool]]
            The data of the table.
    """
    cursor.execute(
        f"""
        SELECT {table_name}.* 
        FROM {table_name} 
        INNER JOIN tables ON tables.name = '{table_name}' 
        WHERE tables.system=false 
        AND tables.type = {str(get_table_type_enumeration_value(table_type))}
        """)

    return cursor.fetchall()


def clean_up(context_id: str):
    """Deletes all tables of any type with name that contain a specific context_id from the monetdb.

        Parameters
        ----------
        context_id : str
            The id of the experiment
    """
    for table_type in ("merge", "remote", "view", "normal"):
        delete_table_by_type_and_context_id(table_type, context_id)
    connection.commit()


@sql_injections_defender
def delete_table_by_type_and_context_id(table_type: str, context_id: str):
    """Deletes all tables of specific type with name that contain a specific context_id from the monetdb.

        Parameters
        ----------
        table_type : str
            The type of the table
        context_id : str
            The id of the experiment
    """
    cursor.execute(
        f"""
        SELECT name, type FROM tables 
        WHERE name LIKE '%{context_id.lower()}%'
        AND tables.type = {str(get_table_type_enumeration_value(table_type))} 
        AND system = false
        """)
    for table in cursor.fetchall():
        if table[1] == 1:
            cursor.execute(f"DROP VIEW {table[0]}")
        else:
            cursor.execute(f"DROP TABLE {table[0]}")
