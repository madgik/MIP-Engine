from typing import List

from mipengine.common.validators import validate_sql_params
from mipengine.node.monetdb_interface.common_actions import get_table_names
from mipengine.node.monetdb_interface.monet_db_connection import MonetDB

DATA_TABLE_PRIMARY_KEY = "row_id"


def get_view_names(context_id: str) -> List[str]:
    return get_table_names("view", context_id)


@validate_sql_params
def create_view(
    view_name: str, pathology: str, datasets: List[str], columns: List[str]
):
    # TODO: Add filters argument
    dataset_names = ",".join(f"'{dataset}'" for dataset in datasets)
    columns = ", ".join(columns)

    MonetDB().execute(
        f"""CREATE VIEW {view_name}
        AS SELECT {DATA_TABLE_PRIMARY_KEY}, {columns}
        FROM {pathology}_data
        WHERE dataset IN ({dataset_names})"""
    )
