from celery import Celery

from mipengine.common.node_catalog import node_catalog
from mipengine.node import config


def get_celery_app(node_id: str):
    node = node_catalog.get_node(node_id)

    rabbitmq_credentials = config.rabbitmq.user + ":" + config.rabbitmq.password
    rabbitmq_url = node.rabbitmqIp + ":" + str(node.rabbitmqPort)
    vhost = config.rabbitmq.vhost

    return Celery(
        "mipengine.node",
        broker=f"amqp://{rabbitmq_credentials}@{rabbitmq_url}/{vhost}",
        backend="rpc://",
        include=[
            "mipengine.node.tasks.tables",
            "mipengine.node.tasks.remote_tables",
            "mipengine.node.tasks.merge_tables",
            "mipengine.node.tasks.common",
        ],
    )


def get_celery_create_table_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.tables.create_table")


def get_celery_get_tables_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.tables.get_tables")


def get_celery_create_view_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.views.create_view")


def get_celery_get_views_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.views.get_views")


def get_celery_create_merge_table_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.merge_tables.create_merge_table")


def get_celery_get_merge_tables_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.merge_tables.get_merge_tables")


def get_celery_create_remote_table_signature(celery_app):
    return celery_app.signature(
        "mipengine.node.tasks.remote_tables.create_remote_table"
    )


def get_celery_get_remote_tables_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.remote_tables.get_remote_tables")


def get_celery_get_table_schema_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.common.get_table_schema")


def get_celery_get_table_data_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.common.get_table_data")


def get_celery_get_udfs_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.udfs.get_udfs")


def get_celery_run_udf_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.udfs.run_udf")


def get_celery_get_run_udf_query_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.udfs.get_run_udf_query")


def get_celery_cleanup_signature(celery_app):
    return celery_app.signature("mipengine.node.tasks.common.clean_up")
