import importlib.resources as pkg_resources
from dataclasses import dataclass
from pathlib import Path
from typing import List
from typing import Union

from dataclasses_json import dataclass_json

from mipengine.common import resources
from mipengine.common.node_exceptions import InvalidNodeId


@dataclass_json
@dataclass
class NodePathology:
    name: str
    datasets: List[str]


@dataclass_json
@dataclass
class NodeData:
    pathologies: List[NodePathology]


@dataclass_json
@dataclass
class Node:
    nodeId: str
    rabbitmqIp: str
    rabbitmqPort: int
    monetdbIp: str
    monetdbPort: int


@dataclass_json
@dataclass
class GlobalNode(Node):
    pass


@dataclass_json
@dataclass
class LocalNode(Node):
    data: NodeData


@dataclass_json
@dataclass
class Nodes:
    globalNode: GlobalNode
    localNodes: List[LocalNode]


class NodeCatalog:
    def __init__(self):
        node_catalog_content = pkg_resources.read_text(resources, "node_catalog.json")
        self._nodes: Nodes = Nodes.from_json(node_catalog_content)

        for local_node in self._nodes.localNodes:
            if not local_node.nodeId.isalnum():
                raise InvalidNodeId(local_node.nodeId)
            if not local_node.nodeId.islower():
                raise ValueError(
                    f"Node id should be lower case, node id = {local_node.nodeId}"
                )

        self._datasets = {}
        for local_node in self._nodes.localNodes:
            for pathology in local_node.data.pathologies:
                if pathology.name not in self._datasets.keys():
                    self._datasets[pathology.name] = pathology.datasets.copy()
                else:
                    self._datasets[pathology.name].extend(pathology.datasets)

        self._nodes_per_dataset = {}
        for local_node in self._nodes.localNodes:
            for pathology in local_node.data.pathologies:
                for dataset in pathology.datasets:
                    if dataset not in self._nodes_per_dataset.keys():
                        self._nodes_per_dataset[dataset] = [local_node]
                    elif local_node not in self._nodes_per_dataset[dataset]:
                        self._nodes_per_dataset[dataset].append(local_node)

    def _save_node_catalog(self):
        resources_folder_path = Path(resources.__file__).parent
        node_catalog_path = Path(resources_folder_path, "node_catalog.json")

        with open(node_catalog_path, 'w') as fp:
            fp.write(self._nodes.to_json())

    def pathology_exists(self, pathology: str) -> bool:
        return pathology in self._datasets.keys()

    def dataset_exists(self, pathology: str, dataset: str) -> bool:
        return dataset in self._datasets[pathology]

    def get_nodes_with_any_of_datasets(self, datasets: List[str]) -> List[LocalNode]:
        if not (nodes := [self._nodes_per_dataset[dataset] for dataset in datasets]):
            raise Exception(f"There are no nodes with any of the datasets->{datasets}")

        local_nodes = [nodes[0][0]]
        for nodes in nodes:
            for node in nodes:
                if node not in local_nodes:
                    local_nodes.append(node)
        return local_nodes

    def get_node(self, node_id: str) -> Union[LocalNode, GlobalNode]:
        if self._nodes.globalNode.nodeId == node_id:
            return self._nodes.globalNode

        try:
            return next(
                local_node
                for local_node in self._nodes.localNodes
                if local_node.nodeId == node_id
            )
        except StopIteration:
            raise ValueError(f"Node ID {node_id} not found in the Node Catalog")

    def set_node(self, node_id, monetdb_ip, monetdb_port, rabbitmq_ip, rabbitmq_port):
        # TODO The pathologies/datasets of the node should also be added dynamically.
        # We are still missing that functionality though so it won't be added yet.

        if self._nodes.globalNode.nodeId == node_id:
            self._nodes.globalNode.monetdbIp = monetdb_ip
            self._nodes.globalNode.monetdbPort = monetdb_port
            self._nodes.globalNode.rabbitmqIp = rabbitmq_ip
            self._nodes.globalNode.rabbitmqPort = rabbitmq_port
            self._save_node_catalog()
            return

        for local_node in self._nodes.localNodes:
            if local_node.nodeId == node_id:
                local_node.monetdbIp = monetdb_ip
                local_node.monetdbPort = monetdb_port
                local_node.rabbitmqIp = rabbitmq_ip
                local_node.rabbitmqPort = rabbitmq_port
                self._save_node_catalog()
                return


node_catalog = NodeCatalog()
