from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app_types import MyState, TaskType
from utils import LoggerInterface, make_retry_call

TASK_DESCRIPTIONS: Dict[TaskType, str] = {
    "data_migration": "This task involves changing, replacing, remapping, or updating assets.",
    "other": "This task does not involve data migration or asset updates.",
}
def make_task_classification_node(logger: LoggerInterface, llm: ChatOpenAI):
    retry_call = make_retry_call(logger)

    def task_classification_node(state: MyState) -> MyState:
        lines = [
            "You are a classifier. Return EXACTLY one identifier from the allowed list.",
            "Allowed identifiers and their meanings:",
        ]
        for task_type, description in TASK_DESCRIPTIONS.items():
            lines.append(f"{task_type} - {description}")
        lines.append(
            "Output must be exactly one of the identifiers, with no punctuation or explanation."
        )
        system_prompt = "\n".join(lines)

        user_prompt = state.get("user_prompt")
        if not user_prompt:
            logger.error("User prompt is empty or not provided.")
            return {**state, "status": "task_classification_failed"}

        response = retry_call(
            lambda: llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
        )

        task_type = str(response.content).strip().lower()
        match task_type:
            case "data_migration":
                logger.info("Data migration detected, proceeding to classification.")
                return {**state, "status": "data_migration_detected"}
            case _:
                logger.error("Task classification failed, stopping processing.")
                logger.info("********************************************************")
                logger.info(user_prompt)
                logger.info("********************************************************")
                return {**state, "status": "task_classification_failed"}

    return task_classification_node
