import json

import pymonetdb
import pytest
import uuid as uuid

from mipengine.common.node_tasks_DTOs import ColumnInfo, TableSchema, TableInfo
from tests.integration_tests import nodes_communication

local_node = nodes_communication.get_celery_app("localnode1")
local_node_create_table = nodes_communication.get_celery_create_table_signature(
    local_node
)
local_node_get_tables = nodes_communication.get_celery_get_tables_signature(local_node)
local_node_get_table_schema = nodes_communication.get_celery_get_table_schema_signature(
    local_node
)
local_node_get_table_data = nodes_communication.get_celery_get_table_data_signature(
    local_node
)
local_node_create_merge_table = (
    nodes_communication.get_celery_create_merge_table_signature(local_node)
)
local_node_create_view = nodes_communication.get_celery_create_view_signature(
    local_node
)
local_node_create_remote_table = (
    nodes_communication.get_celery_create_remote_table_signature(local_node)
)
local_node_cleanup = nodes_communication.get_celery_cleanup_signature(local_node)


@pytest.fixture(autouse=True)
def context_id():
    context_id = "test_sql_injection_" + str(uuid.uuid4()).replace("-", "")

    yield context_id

    local_node_cleanup.delay(context_id=context_id.lower()).get()


def test_sql_injection_get_tables():
    with pytest.raises(ValueError):
        local_node_get_tables.delay(context_id="Robert'); DROP TABLE data; --").get()


def test_sql_injection_get_table_data():
    with pytest.raises(ValueError):
        local_node_get_table_data.delay(
            table_name="Robert'); DROP TABLE data; --"
        ).get()


def test_sql_injection_get_table_schema():
    with pytest.raises(ValueError):
        local_node_get_table_schema.delay(
            table_name="Robert'); DROP TABLE data; --"
        ).get()


def test_sql_injection_create_table(context_id):
    with pytest.raises(ValueError):
        schema = TableSchema(
            [
                ColumnInfo("Robert'); DROP TABLE data; --", "INT"),
                ColumnInfo("col2", "real"),
                ColumnInfo("col3", "text"),
            ]
        )
        json_schema = schema.to_json()
        local_node_create_table.delay(
            context_id=context_id,
            command_id=str(pymonetdb.uuid.uuid1()).replace("-", ""),
            schema_json=json_schema,
        ).get()


def test_sql_injection_create_merge_table(context_id):
    with pytest.raises(ValueError):
        local_node_create_merge_table.delay(
            context_id=context_id,
            command_id=str(pymonetdb.uuid.uuid1()).replace("-", ""),
            table_names=["Robert'); DROP TABLE data; --"],
        ).get()


def test_sql_injection_create_remote_table(context_id):
    with pytest.raises(ValueError):
        schema = TableSchema(
            [
                ColumnInfo("col1", "int"),
                ColumnInfo("col2", "real"),
                ColumnInfo("col3", "text"),
            ]
        )
        table_info = TableInfo("table_name", schema)
        local_node_create_remote_table.delay(
            table_info_json=table_info.to_json(),
            db_socket_address="...:",
        ).get()


def test_sql_injection_create_view(context_id):
    with pytest.raises(ValueError):
        columns = [
            "Robert'); DROP TABLE data; --",
            "age_value",
            "gcs_motor_response_scale",
            "pupil_reactivity_right_eye_result",
        ]
        datasets = ["edsd"]
        pathology = "tbi"
        local_node_create_view.delay(
            context_id=context_id,
            command_id=str(pymonetdb.uuid.uuid1()).replace("-", ""),
            pathology=pathology,
            datasets=datasets,
            columns=columns,
            filters_json="filters",
        ).get()
