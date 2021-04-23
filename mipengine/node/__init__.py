import os

import toml
from importlib.resources import open_text

from mipengine import node
from mipengine.utils import AttrDict

if config_file := os.getenv("CONFIG_FILE"):
    with open(config_file) as fp:
        config = AttrDict(toml.load(fp))
else:
    with open_text(node, "config.toml") as fp:
        config = AttrDict(toml.load(fp))
