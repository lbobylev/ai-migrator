from typing import Dict, List, TypedDict, get_args

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app_types import AssetOperation, AssetType, DataSource, MyState, Operation
from utils import LoggerInterface, make_call_with_self_heal


ASSET_OPERATIONS: Dict[Operation, str] = {
    "create": "Create a new asset.",
    "update": "Update an existing asset.",
    "delete": "Delete an existing asset.",
}

ASSET_TYPES = list(get_args(AssetType))


def make_data_migration_classification_node(logger: LoggerInterface, llm: ChatOpenAI):
    call_with_self_heal = make_call_with_self_heal(logger)

    def data_migration_classification_node(state: MyState) -> MyState:
        lines = [
            "You are a classifier that determines the type of operation with an asset based on the user's request.",
            "Return a JSON object with the key 'operations', containing a list of operations.",
            "Each operation must follow this format:",
            "{",
            "    'asset_type': '<AssetType>',",
            "    'operation': '<Operation>',",
            "    'data_source': '<DataSource>'",
            "    'file_url': '<str>'",
            "}",
            "Where:",
            "- AssetType is one of: " + ", ".join(ASSET_TYPES),
            "- Operation is one of: " + ", ".join(ASSET_OPERATIONS.keys()),
            "- DataSource is one of: " + ", ".join(list(get_args(DataSource))),
            "",
            "Rules for 'data_source':",
            "1. Use 'user_request' ONLY if the request body contains explicit asset-related data (tables, lists, single objects, or fields)",
            "   that directly allow identification or parameterization of the asset (e.g., IDs, names, attributes).",
            "2. If there is NO mention of a file, table, list, object, or any identifiable data tied to the asset type, ALWAYS return 'other'.",
            "3. 'other' must also be used if the request references the asset in general terms without providing concrete, actionable data.",
            "",
            "The asset-related data in the request can be used to:",
            "- Identify objects for update or deletion",
            "- Determine object data for creation",
            "- Match existing assets for retrieval",
            "",
            "The output must be strictly in valid JSON format with no comments, explanations, or extra formatting.",
            "If and only if the request contains an excel file url and the 'data_source' is detected as 'attachment_file',",
            "you should fill the 'file_url' field with the URL of the file parsed from the user request.",
            "Otherwise, the 'file_url' field should be null.",
        ]

        system_prompt = "\n".join(lines)

        user_prompt = state.get("user_prompt")
        if user_prompt is None: 
            logger.error("User input is missing, cannot classify data migration.")
            return {**state, "status": "data_migration_classification_failed"}

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        class ResponseData(TypedDict):
            operations: List[AssetOperation]

        response = call_with_self_heal(messages, llm, ResponseData)
        operations = response["operations"]

        if len(operations) == 0:
            logger.error("No operations detected, stopping processing.")
            return {**state, "status": "data_migration_classification_failed"}

        logger.info(f"Detected operations: {operations}")

        return {
            **state,
            "status": "data_migration_classified",
            "detected_operations": operations,
        }

    return data_migration_classification_node
