import pytest

from mipengine.common.node_tasks_DTOs import TableInfo, TableSchema, ColumnInfo
from mipengine.common.validators import validate_sql_params
from mipengine.common.validators import _validate_sql_param
from mipengine.common.validators import _validate_socket_address
from mipengine.node.monetdb_interface.common_actions import (
    get_table_schema,
    get_table_data,
    get_table_names,
    clean_up,
)
from mipengine.node.monetdb_interface.merge_tables import (
    create_merge_table,
    get_non_existing_tables,
    add_to_merge_table,
    validate_tables_can_be_merged,
)
from mipengine.node.monetdb_interface.remote_tables import create_remote_table
from mipengine.node.monetdb_interface.tables import create_table
from mipengine.node.monetdb_interface.udfs import run_udf
from mipengine.node.monetdb_interface.views import create_view


@pytest.mark.parametrize(
    "args, kwargs",
    [
        (["hello", "world"], {}),
        (["1234", "_name", {"table_name": "ThisTable42"}, ["nested_list"]], {}),
        ([], {"nested": {"dict": {"name": "Bob"}}}),
        ([[["nested"], ["1list"]]], {"nested": {"dict": {"name": "Bob"}}}),
    ],
)
def test_validate_sql_params_wrapper(args, kwargs):
    def returns_true(*args, **kwargs):
        return args, kwargs

    wrapper = validate_sql_params(returns_true)
    assert wrapper(*args, **kwargs)


@pytest.mark.parametrize(
    "args, kwargs",
    [
        ([12345, "world"], {}),
        ([{";nono": "yes"}], {}),
        (["1234", "_name", {"table_name": "--ThisTable42"}, ["nested_list"]], {}),
        ([], {"nested": {"dict": {"name": "evil'ex"}}}),
        ([[["evil'ex"]]], {"nested": {"dict": {"name": "Bob"}}}),
    ],
)
def test_validate_sql_params_wrapper_error(args, kwargs):
    def returns_true(*args, **kwargs):
        return args, kwargs

    wrapper = validate_sql_params(returns_true)
    with pytest.raises(ValueError):
        wrapper(*args, **kwargs)


@pytest.mark.parametrize(
    "arg",
    ["12345", "hello" "__name1234", "this_is_a_name_", "2AF46BE3", "127.0.0.1:1000"],
)
def test_validate_param(arg):
    _validate_sql_param(arg)


@pytest.mark.parametrize(
    "arg",
    [
        "Robert'); DROP TABLE students;--",
        "' or 1=1; --",
        "evil’ex",
        "--123--" "#hashtag",
        "myname@gmail.com",
        "**Important**",
    ],
)
def test_validate_param_error(arg):
    with pytest.raises(ValueError):
        _validate_sql_param(arg)


@pytest.mark.parametrize(
    "arg",
    [
        "192.168.1.51:5000",
        "127.0.0.1:888",
        "0.0.0.0:0",
        "256.256.256.256:65535",
    ],
)
def test_validate_socket_address(arg):
    assert _validate_socket_address(arg)


@pytest.mark.parametrize(
    "arg",
    [
        ".199.23.402:123",
        "123j.123.123.123:12345",
        "...:",
        "hello",
        "-1.23.53.45:-100",
        "12b.43.53h.10:yes",
        "127.00.1:1000",
    ],
)
def test_validate_socket_address_error(arg):
    assert not _validate_socket_address(arg)


table_names_cases = [
    ["table_name", "Robert'); DROP TABLE data; --"],
    ["Robert'); DROP TABLE data; --"],
]

table_info_cases = [
    TableInfo(
        "Robert'); DROP TABLE data; --",
        TableSchema(
            [
                ColumnInfo("col1", "int"),
                ColumnInfo("col2", "real"),
                ColumnInfo("col3", "text"),
            ]
        ),
    ),
    TableInfo(
        "table_name",
        TableSchema(
            [
                ColumnInfo("Robert'); DROP TABLE data; --", "int"),
                ColumnInfo("col2", "real"),
                ColumnInfo("col3", "text"),
            ]
        ),
    ),
]


@pytest.mark.parametrize("table_info", table_info_cases)
def test_create_table_error(table_info):
    with pytest.raises(ValueError):
        create_table(table_info)


@pytest.mark.parametrize("table_info", table_info_cases)
def test_create_merge_table_error(table_info):
    with pytest.raises(ValueError):
        create_merge_table(table_info)


@pytest.mark.parametrize("table_info", table_info_cases)
def test_create_merge_table_error(table_info):
    with pytest.raises(ValueError):
        create_merge_table(table_info)


@pytest.mark.parametrize("table_names", table_names_cases)
def test_get_non_existing_tables_error(table_names):
    with pytest.raises(ValueError):
        get_non_existing_tables(table_names)


@pytest.mark.parametrize(
    "merge_table_name,table_names",
    [
        ("Robert'); DROP TABLE data; --", ["table_name1", "table_name1"]),
        ("merge_table_name", ["Robert'); DROP TABLE data; --", "table_name1"]),
        ("merge_table_name", ["table_name1", "Robert'); DROP TABLE data; --"]),
    ],
)
def test_add_to_merge_table_error(merge_table_name, table_names):
    with pytest.raises(ValueError):
        add_to_merge_table(merge_table_name, table_names)


@pytest.mark.parametrize("table_names", table_names_cases)
def test_validate_tables_can_be_merged_error(table_names):
    with pytest.raises(ValueError):
        validate_tables_can_be_merged(table_names)


@pytest.mark.parametrize(
    "table_names",
    [
        ["table_name", "Robert'); DROP TABLE data; --"],
        ["Robert'); DROP TABLE data; --"],
    ],
)
def test_validate_tables_can_be_merged_error(table_names):
    with pytest.raises(ValueError):
        validate_tables_can_be_merged(table_names)


@pytest.mark.parametrize(
    "table_info,db_socket_address",
    [
        (
            TableInfo(
                "Robert'); DROP TABLE data; --",
                TableSchema(
                    [
                        ColumnInfo("col1", "int"),
                        ColumnInfo("col2", "real"),
                        ColumnInfo("col3", "text"),
                    ]
                ),
            ),
            "db_socket_address",
        ),
        (
            TableInfo(
                "table_name",
                TableSchema(
                    [
                        ColumnInfo("Robert'); DROP TABLE data; --", "int"),
                        ColumnInfo("col2", "real"),
                        ColumnInfo("col3", "text"),
                    ]
                ),
            ),
            "db_socket_address",
        ),
        (
            TableInfo(
                "table_name",
                TableSchema(
                    [
                        ColumnInfo("col1", "int"),
                        ColumnInfo("col2", "real"),
                        ColumnInfo("col3", "text"),
                    ]
                ),
            ),
            "...:",
        ),
    ],
)
def test_create_remote_table_error(table_info, db_socket_address):
    with pytest.raises(ValueError):
        create_remote_table(table_info, db_socket_address)


@pytest.mark.parametrize(
    "view_name,pathology,datasets,columns",
    [
        [
            "Robert'); DROP TABLE data; --",
            "pathology",
            "datasets",
            ["column1", "comuln2"],
        ],
        [
            "view_name",
            "Robert'); DROP TABLE data; --",
            "datasets",
            ["column1", "comuln2"],
        ],
        [
            "view_name",
            "pathology",
            "Robert'); DROP TABLE data; --",
            ["column1", "comuln2"],
        ],
        [
            "view_name",
            "pathology",
            "datasets",
            ["Robert'); DROP TABLE data; --", "comuln2"],
        ],
        [
            "view_name",
            "pathology",
            "datasets",
            ["column1", "Robert'); DROP TABLE data; --"],
        ],
    ],
)
def test_create_view_error(view_name, pathology, datasets, columns):
    with pytest.raises(ValueError):
        create_view(view_name, pathology, datasets, columns)


@pytest.mark.parametrize(
    "udf_creation_stmt, udf_execution_query",
    [
        ["Robert'); DROP TABLE data; --", "Robert'); DROP TABLE data; --"],
    ],
)
def test_run_udf_error(udf_creation_stmt, udf_execution_query):
    with pytest.raises(ValueError):
        run_udf(udf_creation_stmt, udf_execution_query)


@pytest.mark.parametrize(
    "table_name",
    [
        ["Robert'); DROP TABLE data; --"],
    ],
)
def test_get_table_schema_error(table_name):
    with pytest.raises(ValueError):
        get_table_schema(table_name)


@pytest.mark.parametrize(
    "table_name",
    [
        ["Robert'); DROP TABLE data; --"],
    ],
)
def test_get_table_data_error(table_name):
    with pytest.raises(ValueError):
        get_table_data(table_name)


@pytest.mark.parametrize(
    "table_type,context_id",
    [
        ["merge", "Robert'); DROP TABLE data; --"],
        ["Robert'); DROP TABLE data; --", "context_id"],
    ],
)
def test_get_table_names_error(table_type, context_id):
    with pytest.raises(ValueError):
        get_table_names(table_type, context_id)


@pytest.mark.parametrize(
    "context_id",
    [
        ["Robert'); DROP TABLE data; --"],
    ],
)
def test_clean_up_error(context_id):
    with pytest.raises(ValueError):
        clean_up(context_id)
