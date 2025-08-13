from langchain_core.callbacks import BaseCallbackHandler

class GraphLogger(BaseCallbackHandler):
    def on_tool_start(self, tool, input_str, **kwargs):
        tool_name = tool["name"]
        print(f"[TOOL START] {tool_name} with input: {input_str}")

    def on_tool_end(self, output, **kwargs):
        # print(f"[TOOL END] Output: {output}")
        print("[TOOL END]")

    # def on_llm_start(self, serialized, prompts, **kwargs):
    #     truncated_prompts = [prompt[:300] for prompt in prompts]
    #     print(f"[LLM START] Prompts:\n{truncated_prompts}")
    #
    # def on_llm_end(self, response, **kwargs):
    #     truncated_response = response[:300] if isinstance(response, str) else response
    #     print(f"[LLM END] Response:\n{truncated_response}")
