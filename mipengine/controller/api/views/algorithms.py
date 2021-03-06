import logging
import traceback

from quart import Blueprint
from quart import request

from mipengine.controller.api.DTOs.AlgorithmSpecificationsDTOs import AlgorithmSpecificationDTO
from mipengine.controller.api.DTOs.AlgorithmSpecificationsDTOs import algorithm_specificationsDTOs
from mipengine.controller.api.errors.exceptions import BadRequest
from mipengine.controller.api.errors.exceptions import BadUserInput
from mipengine.controller.api.services.validate_algorithm import validate_algorithm

from mipengine.controller.api.DTOs.AlgorithmRequestDTO import AlgorithmInputDataDTO, AlgorithmRequestDTO
from mipengine.controller.algorithm_executor.AlgorithmExecutor import AlgorithmExecutor

import asyncio

import concurrent.futures


algorithms = Blueprint('algorithms_endpoint', __name__)


@algorithms.route("/algorithms")
async def get_algorithms() -> str:
    algorithm_specifications = algorithm_specificationsDTOs.algorithms_list

    return AlgorithmSpecificationDTO.schema().dumps(algorithm_specifications, many=True)


@algorithms.route("/algorithms/<algorithm_name>", methods=['POST'])
async def post_algorithm(algorithm_name: str) -> str:
    logging.info(f"Algorithm execution with name {algorithm_name}.")

    request_body = await request.data

    # try:
    #     validate_algorithm(algorithm_name, request_body)
    # except (BadRequest, BadUserInput) as exc:
    #     raise exc
    # except:
    #     logging.error(f"Unhandled exception: \n {traceback.format_exc()}")
    #     raise BadRequest("Algorithm validation failed.")

    try:
        algorithm_request = AlgorithmRequestDTO.from_json(request_body)

        # TODO: This looks freakin awful...
        # Function run_algorithm_executor_in_threadpool calls the run method on the AlgorithmExecutor on a separate thread
        # This function is queued in the running event loop
        # Thus AlgorithmExecutor.run is executed asynchronoysly and does not block further requests to the server
        def run_algorithm_executor_in_threadpool(algorithm_name, algorithm_request):
            alg_ex = AlgorithmExecutor(algorithm_name, algorithm_request)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(alg_ex.run)
                result = future.result()
                return result

        loop = asyncio.get_running_loop()
        algorithm_result = await loop.run_in_executor(None, run_algorithm_executor_in_threadpool, algorithm_name, algorithm_request)
        return str(algorithm_result)

    except:
        logging.error(f"Unhandled exception: \n {traceback.format_exc()}")
        raise BadRequest("Something went wrong. "
                         "Please inform the system administrator or try again later.")

    return "Something did not go quite right...?"