from typing import List

from mipengine.common.node_tasks_DTOs import TableInfo


class TablesNotFound(Exception):
    """
    Exception raised for errors while retrieving a table from a database.

    Attributes:
        tables -- tables which caused the error
        message -- explanation of the error
    """

    def __init__(self, tables: List[str]):
        self.tables = tables
        self.message = f"The following tables were not found : {tables}"
        super().__init__(self.message)


class IncompatibleSchemasMergeException(Exception):
    """Exception raised for errors while trying to merge tables with incompatible schemas.

    Attributes:
        table -- table which caused the error
        message -- explanation of the error
    """

    def __init__(self, table_infos: List[TableInfo]):
        self.table_infos = table_infos
        self.message = (
            f"Tables to be added doesn't match MERGE TABLE schema : {table_infos}"
        )
        super().__init__(self.message)


class IncompatibleTableTypes(Exception):
    """Exception raised for errors while trying to merge tables with incompatible table types.

    Attributes:
        table_types --  the types of the table which caused the error
        message -- explanation of the error
    """

    def __init__(self, table_types: List[str]):
        self.table_types = table_types
        self.message = f"Tables have more than one distinct types : {self.table_types}"
        super().__init__(self.message)


class InvalidNodeId(Exception):
    """Exception raised while checking the validity of a node id.

    Attributes:
        node_id --  the id of the node which caused the error
        message -- explanation of the error
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.message = f"Invalid node id .Node id is : {self.node_id}. Node id should be alphanumeric."
        super().__init__(self.message)
