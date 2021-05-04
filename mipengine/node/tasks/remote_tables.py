from typing import List

from celery import shared_task

from mipengine.common.node_tasks_DTOs import TableInfo
from mipengine.node.monetdb_interface import remote_tables


@shared_task
def get_remote_tables(context_id: str) -> List[str]:
    """
    Parameters
    ----------
    context_id : str
    The id of the experiment

    Returns
    ------
    List[str]
        A list of remote table names
    """
    return remote_tables.get_remote_table_names(context_id)


@shared_task
def create_remote_table(table_info_json: str, db_socket_address: str):
    """
    Parameters
    ----------
    table_info_json : str(TableInfo)
        A TableInfo object in a jsonified format
    db_socket_address : str
        The db_socket_address of the monetdb that we want to create the remote table from.
    """
    table_info = TableInfo.from_json(table_info_json)
    remote_tables.create_remote_table(
        table_info=table_info,
        db_socket_address=db_socket_address,
    )
