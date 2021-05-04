from contextlib import contextmanager
from typing import List

import pymonetdb

from mipengine import config
from mipengine.common.node_catalog import node_catalog

OCC_MAX_ATTEMPTS = 50


class Singleton(type):
    """
    Copied from https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class MonetDB(metaclass=Singleton):
    """
    MonetDB is a Singleton class because we want it to be initialized at runtime.

    If the connection is a public module variable, it will be initialized at import time
    from Celery and all the Celery workers will use the same connection instance.

    We want one MonetDB connection instance per Celery worker/process.

    """

    def __init__(self):
        global_node = node_catalog.get_global_node()
        if global_node.nodeId == config.node.identifier:
            node = global_node
        else:
            node = node_catalog.get_local_node(config.node.identifier)
        monetdb_hostname = node.monetdbHostname
        monetdb_port = node.monetdbPort
        self._connection = pymonetdb.connect(
            username=config.monetdb.username,
            port=monetdb_port,
            password=config.monetdb.password,
            hostname=monetdb_hostname,
            database=config.monetdb.database,
        )

    @contextmanager
    def cursor(self):
        try:
            cur = self._connection.cursor()
            yield cur
        except Exception as exc:
            raise exc
        finally:
            cur.close()

    def execute_with_result(self, query: str) -> List:
        """
        Used to execute select queries that return a result.

        Should NOT be used to execute "CREATE, DROP, ALTER, UPDATE, ..." statements.
        """

        # We use a single instance of a connection and by committing before a select query we refresh the state of the connection
        # So that it sees changes from other processes/connections.
        # https://stackoverflow.com/questions/9305669/mysql-python-connection-does-not-see-changes-to-database-made-on-another-connect.
        self._connection.commit()

        with self.cursor() as cur:
            cur.execute(query)
            result = cur.fetchall()
            return result

    def execute(self, query: str):
        """
        Executes statements that don't have a result. For example "CREATE,DROP,UPDATE".
        And handles the *Optimistic Concurrency Control by giving each call X attempts
        if they fail with pymonetdb.exceptions.IntegrityError .
        *https://www.monetdb.org/blog/optimistic-concurrency-control
        """

        for _ in range(OCC_MAX_ATTEMPTS):
            with self.cursor() as cur:
                try:
                    cur.execute(query)
                    self._connection.commit()
                    break
                except pymonetdb.exceptions.IntegrityError as exc:
                    integrity_error = exc
                    self._connection.rollback()
                    continue
                except Exception as exc:
                    self._connection.rollback()
                    raise exc
        else:
            raise integrity_error
