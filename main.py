import json
from typing import Any, Callable, Dict, List, Tuple

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app_types import (
    AssetOperation,
    AssetType,
    MyState,
    Operation,
)
from logger import GraphLogger
from nodes.data_migration_classification_node import (
    make_data_migration_classification_node,
)
from nodes.task_classification_node import make_task_classification_node
from nodes.user_input_processing_node import make_user_input_processing_node
from file_utils import read_excel, select_file
from utils import get_logger, make_call_with_self_heal, make_retry_call
from dotenv import load_dotenv
from github_utils import get_issue, get_issues
import asyncio
import requests
from urllib.parse import urlparse
import os


load_dotenv()
graphLogger = GraphLogger()
logger = get_logger()
retry_call = make_retry_call(logger)
call_with_self_heal = make_call_with_self_heal(logger)
fast_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
smart_llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

OperationHandler = Callable[[AssetOperation], Any]
OPERATION_HANDLERS: Dict[Tuple[AssetType, Operation], OperationHandler] = {}


def register_handler(asset_type: AssetType, operation: Operation) -> Callable:
    def deco(fn: OperationHandler) -> OperationHandler:
        OPERATION_HANDLERS[(asset_type, operation)] = fn
        return fn

    return deco


@register_handler("BaseMaterial", "update")
def handle_base_material_update(op: AssetOperation) -> Any:
    if op.data_source == "attachment_file":
        if not op.data:
            raise ValueError("Data is required for attachment_file operations.")
    else:
        logger.info("Not implemented for data_source: %s", op.data_source)
    return {"status": "ok", "details": f"BaseMaterial updated from {op.data_source}"}


@register_handler("GalvanicTreatment", "update")
def handle_galvanic_treatment_update(op: AssetOperation) -> Any:
    print(op)
    return {
        "status": "ok",
        "details": f"GalvanicTreatment updated from {op.data_source}",
    }


@register_handler("ComponentReference", "update")
def component_reference_update(op: AssetOperation) -> Any:
    print(op)
    return {
        "status": "ok",
        "details": f"ComponentReference updated from {op.data_source}",
    }


def operation_plan_init_node(state: MyState) -> MyState:
    ops = state.get("detected_operations") or []

    return {
        **state,
        "results": [],
        "errors": [],
        "total": len(ops),
        "done": 0,
    }


def download_file(url, dest=None):
    if dest and os.path.exists(dest):
        logger.info(f"File {dest} already exists, skipping download.")
        return dest
    cookie_str = os.getenv("GITHUB_COOKIE", "")
    cookies = dict(item.split("=", 1) for item in cookie_str.split("; "))
    if dest is None:
        dest = os.path.basename(urlparse(url).path) or "download.bin"

    response = requests.get(url, cookies=cookies, stream=True)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return dest

    

def operation_plan_fanout_node(state: MyState) -> List[Send]:
    ops = state.get("detected_operations") or []
    sends = [
        Send("operation_worker_node", {"op": op, "op_index": i})
        for i, op in enumerate(ops)
    ]
    return sends


def operation_worker_node(state: MyState) -> MyState:
    op = state.get("op")
    if not op:
        return {"errors": [{"error": "No op in state"}], "done": 1}

    if op["data_source"] == "attachment_file":
        try:
            file_path = download_file(op["file_url"])
            op["data"] = read_excel(file_path)
        except requests.RequestException as e:
            logger.error(f"Failed to download file from {op['file_url']}: {e}")
            return {
                "errors": [{"error": str(e), "op": op}],
            }

    key = (op["asset_type"], op["operation"])
    handler = OPERATION_HANDLERS.get(key)
    if handler is None:
        return {"errors": [{"op": op, "error": "No handler found"}], "done": 1}

    try:
        payload = handler(op)
        op_index = state.get("op_index")
        res = {
            "index": op_index,
            "asset_type": op.asset_type,
            "operation": op.operation,
            **payload,
        }
        return {"results": [res], "done": 1}
    except Exception as e:
        return {
            "errors": [{"op": op, "error": str(e)}],
            "done": 1,
        }


def operation_gather_node(state: MyState):
    done = state.get("done") or 0
    total = state.get("total") or 0
    if done >= total:
        return state


def route_by_status(state: MyState) -> str:
    match state.get("status"):
        case "data_migration_detected":
            return "data_migration_classification_node"
        case "data_migration_classified":
            return "operation_plan_init_node"
    logger.error("Task is not recognized, routing to END.")
    return END


graph = StateGraph(MyState)
graph.add_node(
    "user_input_processing_node", make_user_input_processing_node(logger, fast_llm)
)
graph.add_node(
    "task_classification_node", make_task_classification_node(logger, fast_llm)
)
graph.add_node(
    "data_migration_classification_node",
    make_data_migration_classification_node(logger, fast_llm),
)
graph.add_node(
    "operation_plan_init_node",
    operation_plan_init_node,
)
graph.add_node(
    "operation_plan_fanout_node",
    operation_plan_fanout_node,
)
graph.add_node(
    "operation_worker_node",
    operation_worker_node,
)
graph.add_node(
    "operation_gather_node",
    operation_gather_node,
)
graph.add_edge(START, "user_input_processing_node")
graph.add_edge("user_input_processing_node", "task_classification_node")
graph.add_conditional_edges(
    "task_classification_node",
    route_by_status,
    ["data_migration_classification_node", END],
)
graph.add_conditional_edges(
    "data_migration_classification_node",
    route_by_status,
    ["operation_plan_init_node", END],
)
graph.add_conditional_edges("operation_plan_init_node", operation_plan_fanout_node)
graph.add_edge("operation_plan_fanout_node", "operation_worker_node")
graph.add_edge("operation_worker_node", "operation_gather_node")
graph.add_conditional_edges(
    "operation_gather_node",
    lambda s: END if s["done"] >= s["total"] else "operation_gather_node",
)
app = graph.compile()

user_input = """
We’d need to change the mapping of the base materials listed in the attached file.

Expected result: substitute the “OLD Base Material KEYE Key” (column G in the attached file) with “NEW Base Material KEYE Key” (column K in the attached file).
We expect that all components that have one or more of the base materials mentioned in the attached file will be consequently updated.
"""


def dump(x):
    print(json.dumps(x, indent=4, ensure_ascii=False))


def load_data():
    file_path = select_file.invoke({})
    data = read_excel.invoke({"file_path": file_path})
    return data


def run_task_classification_node():
    return make_task_classification_node(logger, fast_llm)(
        {
            "user_prompt": user_input,
            "user_input": user_input,
            "status": "other",
            "task_data": None,
        }
    )


def run_data_migration_classification_node():
    prompt = """
Create new Eyewears. Update Base Matarials listed in the attached file.
Also some Acetates should be deleted.
"""
    return make_data_migration_classification_node(logger, smart_llm)(
        {
            "user_prompt": user_input,
            "user_input": user_input,
            "status": "data_migration_detected",
            "task_data": None,
        }
    )


async def main():
    issues = get_issues()

    await app.abatch(
        [{"issue": issue, "status": "other"} for issue in issues],
        config={"callbacks": [graphLogger], "recursion_limit": 30},
    )


if __name__ == "__main__":
    # asyncio.run(main())
    issue = get_issue(607)
    app.invoke(
        {"issue": issue, "status": "other"},
        config={"callbacks": [graphLogger], "recursion_limit": 30},
    )
