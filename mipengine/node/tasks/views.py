import json
from typing import List

from celery import shared_task

from mipengine.node.monetdb_interface import views
from mipengine.node.monetdb_interface.common import config
from mipengine.node.monetdb_interface.common import create_table_name
from mipengine.node.tasks.data_classes import ColumnInfo
from mipengine.node.tasks.data_classes import TableData


@shared_task
def get_views(context_id: str) -> List[str]:
    """
        Parameters
        ----------
        context_id : str
            The id of the experiment

        Returns
        ------
        str
            A list of view names in a jsonified format
    """
    return json.dumps(views.get_views_names(context_id))


@shared_task
def get_view_schema(view_name: str) -> List[ColumnInfo]:
    """
        Parameters
        ----------
        view_name : str
            The name of the view

        Returns
        ------
        A schema(list of ColumnInfo's objects) in a jsonified format
    """
    schema = views.get_view_schema(view_name)
    return ColumnInfo.schema().dumps(schema, many=True)


@shared_task
def get_view_data(view_name: str) -> TableData:
    """
        Parameters
        ----------
        view_name : str
        The name of the view

        Returns
        ------
        str
            An object of TableData in a jsonified format
    """
    schema = views.get_view_schema(view_name)
    data = views.get_view_data(view_name)
    return TableData(schema, data).to_json()


@shared_task
def create_view(context_id: str, columns: str, datasets: str) -> str:
    """
        Parameters
        ----------
        context_id : str
            The id of the experiment
        columns : str
            A list of column names in a jsonified format
        datasets : str
            A list of dataset names in a jsonified format

        Returns
        ------
        str
            The name of the created view in lower case
    """
    view_name = create_table_name("view", context_id, config["node"]["identifier"])
    views.create_view(view_name, json.loads(columns), json.loads(datasets))
    return view_name.lower()
