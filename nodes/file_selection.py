from app_types import MyState
from tools.file_utils import select_file
from utils import LoggerInterface


def make_file_selection_node(logger: LoggerInterface):
    def file_selection_node(state: MyState) -> MyState:
        file_path = select_file.invoke({})
        if not file_path:
            logger.error("File selection failed, stopping processing.")
            return {**state, "status": "file_selection_failed"}
        task_data = state.get("task_data") or {}
        return {
            **state,
            "status": "file_selected",
            "task_data": {**task_data, "file_path": file_path},
        }

    return file_selection_node
