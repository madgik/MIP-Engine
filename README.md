# MIP-Engine

### Prerequisites

1. Install [python3.8](https://www.python.org/downloads/ "python3.8")

1. Install [poetry](https://python-poetry.org/ "poetry")
   It is important to install `poetry` in isolation, so follow the
   recommended installation method.

## Setup

#### Environment Setup

1. Install dependencies

   ```
   poetry install
   ```

1. Activate virtual environment

   ```
   poetry shell
   ```

1. *Optional* To install tab completion for `invoke` run  (replacing `bash` with your shell)

   ```
   source <(poetry run inv --print-completion-script bash)
   ```

1. *Optional* `pre-commit` is included in development dependencies. To install hooks

   ```
   pre-commit install
   ```

#### Local Deployment

1. Find your machine's local ip address, *e.g.* with

   ```
   ifconfig | grep "inet "
   ```

1. Create a deployment configuration

   ```
   inv config --ip <YOUR-IP> --node-name <NODE-NAME> --monetdb-port <MONETDB_PORT> --rabbitmq-port <RABBITMQ_PORT>
   ```

   Append as many `--node-name`, `--monetdb-port`, `rabbitmq-port` triplets as you want.

1. Deploy everything with

   ```
   inv deploy --start-controller --start-nodes
   ```

1. Attach to some service's stdout/stderr with

   ```
   inv attach --controller
   ```

   or

   ```
   inv attach --node <NODE-NAME>
   ```

#### Algorithm Run

1. Make a post request, *e.g.*
   ```
   python test_post_request.py
   ```
