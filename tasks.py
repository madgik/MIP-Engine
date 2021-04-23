import sys
from enum import Enum
from itertools import cycle
from os import listdir
from os import path
from pathlib import Path
from textwrap import indent
from time import sleep

import toml
from invoke import UnexpectedExit
from invoke import task
from termcolor import colored

PROJECT_ROOT = Path(__file__).parent
print(PROJECT_ROOT)
DEPLOYMENT_CONFIG_FILE = PROJECT_ROOT / ".deployment.toml"
NODES_CONFIG_DIR = PROJECT_ROOT / "configs/nodes/"
NODE_CONFIG_TEMPLATE_FILE = PROJECT_ROOT / "mipengine/node/config.toml"
OUTDIR = Path("/tmp/mipengine/")
if not OUTDIR.exists():
    OUTDIR.mkdir()


# TODO Add pre-tasks when this is implemented https://github.com/pyinvoke/invoke/issues/170
# Right now if we call a task from another task, the "pre"


@task
def create_node_configs(c):
    """
    This command, using the .deployment.toml file, will create the node configuration files.
    """

    if not path.isfile(DEPLOYMENT_CONFIG_FILE):
        raise FileNotFoundError("Deployment config file '.deployment.toml' not found.")

    with open(DEPLOYMENT_CONFIG_FILE) as fp:
        deployment_config = toml.load(fp)

    with open(NODE_CONFIG_TEMPLATE_FILE) as fp:
        template_node_config = toml.load(fp)

    for node in deployment_config["nodes"]:
        node_config = template_node_config.copy()
        node_config["identifier"] = node["id"]
        node_config["log_level"] = deployment_config["log_level"]
        node_config["monetdb"]["ip"] = deployment_config["ip"]
        node_config["monetdb"]["port"] = node["monetdb_port"]
        node_config["rabbitmq"]["ip"] = deployment_config["ip"]
        node_config["rabbitmq"]["port"] = node["rabbitmq_port"]

        Path(NODES_CONFIG_DIR).mkdir(parents=True, exist_ok=True)
        node_config_file = NODES_CONFIG_DIR / f"{node['id']}.toml"
        with open(node_config_file, "w+") as fp:
            toml.dump(node_config, fp)


@task
def install_dependencies(c):
    """Install project dependencies using poetry"""
    message("Installing dependencies...", Level.HEADER)
    cmd = "poetry install"
    run(c, cmd)


@task
def rm_containers(c, monetdb=False, rabbitmq=False):
    """Remove containers

    Removes all containers having either monetdb or rabbitmq in the name."""
    names = []
    if monetdb:
        names.append("monetdb")
    if rabbitmq:
        names.append("rabbitmq")
    if not names:
        message(
            "You must specify at least one container family to remove (monetdb or/and rabbitmq)",
            level=Level.WARNING,
        )
    for name in names:
        container_ids = c.run(f"docker ps -qa --filter name={name}", hide="out")
        if container_ids.stdout:
            message(f"Removing {name} containers...", Level.HEADER)
            cmd = f"docker rm -vf $(docker ps -qa --filter name={name})"
            run(c, cmd)
        else:
            message(f"No {name} container to remove", level=Level.HEADER)


@task(iterable=["port"])
def start_monetdb(c, port, monetdb_image=None):
    """Start MonetDB container(s) on given port(s)"""
    rm_containers(c, monetdb=True)

    if not monetdb_image:
        monetdb_image = get_deployment_config("monetdb_image")

    ports = port
    for i, port in enumerate(ports):
        container_ports = f"{port}:50000"
        container_name = f"monetdb-{i}"
        message(
            f"Starting container {container_name} on ports {container_ports}...",
            Level.HEADER,
        )
        cmd = f"docker run -d -P -p {container_ports} --name {container_name} {monetdb_image}"
        run(c, cmd)


@task(iterable=["port"])
def load_data(c, port=None):
    """Load data into DB from csv

    If the port is not set, the configurations inside the `./configs/nodes` folder
    will be used to load the data in the nodes. The data will be imported on nodes
    that have the `local` keyword in their name."""

    local_node_ports = port
    if not local_node_ports:
        config_files = [NODES_CONFIG_DIR / file for file in listdir(NODES_CONFIG_DIR)]
        if not config_files:
            message(
                f"There are no node config files to be used for data import. Folder: {NODES_CONFIG_DIR}",
                Level.WARNING,
            )
            sys.exit(1)

        local_node_ports = []
        for node_config_file in config_files:
            with open(node_config_file) as fp:
                node_config = toml.load(fp)
            if "local" in node_config["identifier"]:
                local_node_ports.append(node_config["monetdb"]["port"])

    from tests import integration_tests

    data_folder = path.dirname(integration_tests.__file__) + "/data"
    with open(NODE_CONFIG_TEMPLATE_FILE) as fp:
        template_node_config = toml.load(fp)
    for port in local_node_ports:
        message(f"Loading data on MonetDB at port {port}...", Level.HEADER)
        cmd = (
            f"poetry run python -m mipengine.node.monetdb_interface.csv_importer "
            f"-folder {data_folder} "
            f"-user {template_node_config['monetdb']['username']} "
            f"-pass {template_node_config['monetdb']['password']} "
            f"-url localhost:{port} "
            f"-farm db"
        )
        run(c, cmd)


@task(iterable=["port"])
def config_rabbitmq(c, port):
    """Configure users and permissions for RabbitMQ containers on given port(s)"""
    message("Configuring RabbitMQ containers, this may take some time", Level.HEADER)

    with open(NODE_CONFIG_TEMPLATE_FILE) as fp:
        node_config = toml.load(fp)
    rabbitmqctl_cmds = [
        f"add_user {node_config['rabbitmq']['user']} {node_config['rabbitmq']['password']}",
        f"add_vhost {node_config['rabbitmq']['vhost']}",
        f"set_user_tags {node_config['rabbitmq']['user']} user_tag",
        f"set_permissions -p {node_config['rabbitmq']['vhost']} {node_config['rabbitmq']['user']} '.*' '.*' '.*'",
    ]
    ports = port
    for num, port in enumerate(ports):
        container_name = f"rabbitmq-{num}"

        for rmq_cmd in rabbitmqctl_cmds:
            message(
                f"Configuring container {container_name}: rabbitmqctl {rmq_cmd}...",
                Level.HEADER,
            )
            cmd = f"docker exec {container_name} rabbitmqctl {rmq_cmd}"
            for _ in range(30):
                try:
                    run(c, cmd, raise_error=True)
                except UnexpectedExit:
                    spin_wheel(time=2)
                else:
                    break
            else:
                message("Cannot configure RabbitMQ", Level.ERROR)
                sys.exit(1)


@task(iterable=["port"])
def start_rabbitmq(c, port):
    """Start RabbitMQ container(s) on given port(s)"""
    rm_containers(c, rabbitmq=True)
    ports = port
    for i, port in enumerate(ports):
        container_name = f"rabbitmq-{i}"
        container_ports = f"{port}:5672"
        message(
            f"Starting container {container_name} on ports {container_ports}...",
            Level.HEADER,
        )
        cmd = f"docker run -d -p {container_ports} --name {container_name} rabbitmq"
        run(c, cmd)


@task
def kill_node(c, node=None, all_=False):
    """Kill Celery node

    The method always tries two commands, one for cases where node was
    started using the celery binary and one for cases it was started
    as a python module.

    In order for the node processes to be killed, we need to kill both
    the parent process with the 'node_identifier' and it's child."""

    if all_:
        node_pattern = ""
    elif node:
        node_pattern = node
    else:
        message("Please specify a node using --node <node> or use --all", Level.WARNING)
        sys.exit(1)
    node_descr = f" {node_pattern}" if node_pattern else "s"
    res_bin = c.run(
        f"ps aux | grep '[c]elery' | grep 'worker' | grep '{node_pattern}' ",
        hide="both",
        warn=True,
    )
    res_py = c.run(
        f"ps aux | grep '[m]ipengine' | grep 'worker' | grep '{node_pattern}'",
        hide="both",
        warn=True,
    )
    if res_bin.ok:
        message(
            f"Killing previous celery instance{node_descr} started using celery binary...",
            Level.HEADER,
        )
        cmd = (
            f"pid=$(ps aux | grep '[c]elery' | grep 'worker' | grep '{node_pattern}' | awk '{{print $2}}') "
            f"&& pgrep -P $pid | xargs kill -9 "
            f"&& kill -9 $pid "
        )
        c.run(cmd)
    if res_py.ok:
        message(
            f"Killing previous celery instance{node_descr} started as a python module...",
            Level.HEADER,
        )
        cmd = (
            f"pid=$(ps aux | grep '[m]ipengine' | grep 'worker' | grep '{node_pattern}' | awk '{{print $2}}') "
            f"&& pgrep -P $pid | xargs kill -9"
            f"&& kill -9 $pid"
        )
        run(c, cmd)
    if not res_bin.ok and not res_py.ok:
        message("No celery instances found", Level.HEADER)


@task
def start_node(c, node=None, all_=False, celery_log_level=None, detached=False):
    """Start Celery node(s)

    A node is started using the appropriate file inside the ./configs/nodes folder.
    A file with the same name as the node should exist.

    If the --all argument is given, the nodes of which the configuration file exists, will be started."""

    if not celery_log_level:
        celery_log_level = get_deployment_config("celery_log_level")

    node_ids = []
    if all_:
        for node_config_file in listdir(NODES_CONFIG_DIR):
            filename, file_ext = path.splitext(node_config_file)
            node_ids.append(filename)
    elif node:
        node_config_file = NODES_CONFIG_DIR / f"{node}.toml"
        if not path.isfile(node_config_file):
            message(
                f"The configuration file for node '{node}', does not exist in directory '{NODES_CONFIG_DIR}'",
                Level.ERROR,
            )
            sys.exit(1)
        filename, file_ext = path.splitext(path.basename(node_config_file))
        node_ids.append(filename)
    else:
        message("Please specify a node using --node <node> or use --all", Level.WARNING)
        sys.exit(1)

    for node_id in node_ids:
        kill_node(c, node_id)

        message(f"Starting Node {node_id}...", Level.HEADER)
        node_config_file = NODES_CONFIG_DIR / f"{node_id}.toml"
        with c.prefix(
            f"export CONFIG_FILE={node_config_file} PYTHONPATH={PROJECT_ROOT}"
        ):
            outpath = OUTDIR / (node_id + ".out")
            if detached or all_:
                cmd = f"poetry run python -m mipengine.node.node worker -l {celery_log_level} >> {outpath} 2>&1"
                c.run(cmd, disown=True)
                spin_wheel(time=4)
                message("Ok", Level.SUCCESS)
            else:
                cmd = f"poetry run python -m mipengine.node.node worker -l {celery_log_level}"
                c.run(cmd)


@task
def kill_controller(c):
    """Kill Controller"""
    message("Killing Controller...", Level.HEADER)
    res = c.run("ps aux | grep '[q]uart'", hide="both", warn=True)
    if res.ok:
        message("Killing previous Quart instances...", Level.HEADER)
        cmd = "ps aux | grep '[q]uart' | awk '{ print $2}' | xargs kill -9 && sleep 5"
        run(c, cmd)
    else:
        message("No quart instance found", Level.HEADER)


@task
def start_controller(c, detached=False):
    """Start Controller"""
    kill_controller(c)

    message("Starting Controller...", Level.HEADER)
    with c.prefix(
        "export QUART_APP=mipengine/controller/api/app:app  PYTHONPATH={PROJECT_ROOT}"
    ):
        outpath = OUTDIR / "controller.out"
        if detached:
            cmd = f"poetry run quart run >> {outpath} 2>&1"
            c.run(cmd, disown=True)
            spin_wheel(time=4)
            message("Ok", Level.SUCCESS)
        else:
            cmd = f"poetry run quart run"
            c.run(cmd)


@task
def deploy(
    c,
    install_dep=True,
    start_all=False,
    start_controller_=False,
    start_nodes=False,
    celery_log_level=None,
    monetdb_image=None,
):
    """(Re)Deploy everything.
    The nodes will be deployed using the existing node config files."""

    if not celery_log_level:
        celery_log_level = get_deployment_config("celery_log_level")

    if not monetdb_image:
        monetdb_image = get_deployment_config("monetdb_image")

    if install_dep:
        install_dependencies(c)

    if start_controller_ or start_all:
        start_controller(c, detached=True)

    config_files = [NODES_CONFIG_DIR / file for file in listdir(NODES_CONFIG_DIR)]
    if not config_files:
        message(
            f"There are no node config files to be used for deployment. Folder: {NODES_CONFIG_DIR}",
            Level.WARNING,
        )
        sys.exit(1)

    monetdb_ports = []
    rabbitmq_ports = []
    for node_config_file in config_files:
        with open(node_config_file) as fp:
            node_config = toml.load(fp)
        monetdb_ports.append(node_config["monetdb"]["port"])
        rabbitmq_ports.append(node_config["rabbitmq"]["port"])

    start_monetdb(c, port=monetdb_ports, monetdb_image=monetdb_image)
    start_rabbitmq(c, port=rabbitmq_ports)
    config_rabbitmq(c, port=rabbitmq_ports)

    if start_nodes or start_all:
        start_node(c, all_=True, celery_log_level=celery_log_level, detached=True)


@task
def attach(c, node=None, controller=False, db=None):
    """Attach to Node, Controller or DB"""
    if (node or controller) and not (node and controller):
        fname = node or "controller"
        outpath = OUTDIR / (fname + ".out")
        cmd = f"tail -f {outpath}"
        c.run(cmd)
    elif db:
        c.run(f"docker exec -it {db} mclient db", pty=True)
    else:
        message("You must attach to Node, Controller or DB", Level.WARNING)
        sys.exit(1)


@task
def cleanup(c):
    """Kill Controller and Nodes, remove MonetDB and RabbitMQ containers"""
    kill_controller(c)
    kill_node(c, all_=True)
    rm_containers(c, monetdb=True, rabbitmq=True)
    if OUTDIR.exists():
        message(f"Removing {OUTDIR}...", level=Level.HEADER)
        for outpath in OUTDIR.glob("*.out"):
            outpath.unlink()
        OUTDIR.rmdir()
        message("Ok", level=Level.SUCCESS)


def run(c, cmd, finish=True, error_check=True, raise_error=False):
    promise = c.run(cmd, asynchronous=True)
    spin_wheel(promise=promise)
    stderr = promise.runner.stderr
    if error_check and stderr:
        if raise_error:
            raise UnexpectedExit(stderr)
        message("Error", Level.ERROR)
        message("\n".join(stderr), Level.BODY)
        sys.exit(promise.runner.returncode())
    elif finish:
        message("Ok", Level.SUCCESS)


class Level(Enum):
    HEADER = ("cyan", 1)
    BODY = ("white", 2)
    SUCCESS = ("green", 1)
    ERROR = ("red", 1)
    WARNING = ("yellow", 1)


def message(msg, level=Level.BODY):
    if msg.endswith("..."):
        end = ""
    else:
        end = "\n"
    color, indent_level = level.value
    prfx = "  " * indent_level
    msg = colored(msg, color)
    print(indent(msg, prfx), end=end, flush=True)


wheel = cycle(r"-\|/")


def spin_wheel(promise=None, time=None):
    dt = 0.15
    if promise is not None:
        print("  ", end="")
        for frame in wheel:
            print(frame + "  ", sep="", end="", flush=True)
            sleep(dt)
            print("\b\b\b", sep="", end="", flush=True)
            if promise.runner.process_is_finished:
                print("\b\b", end="")
                break
    elif time:
        print("  ", end="")
        for frame in wheel:
            print(frame + "  ", sep="", end="", flush=True)
            sleep(dt)
            print("\b\b\b", sep="", end="", flush=True)
            time -= dt
            if time <= 0:
                print("\b\b", end="")
                break


def get_deployment_config(config):
    if not path.isfile(DEPLOYMENT_CONFIG_FILE):
        raise FileNotFoundError(
            f"Please provide a --{config} parameter or create a deployment config file '.deployment.toml'"
        )

    with open(DEPLOYMENT_CONFIG_FILE) as fp:
        return toml.load(fp)[config]
