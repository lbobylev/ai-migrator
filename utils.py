import time
import random
import json
from typing import Callable, TypeVar, Protocol, Any
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)
import logging


class LoggerInterface(Protocol):
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


T = TypeVar("T")

TRANSIENT_MARKERS = ("timeout", "rate limit", "overloaded", "temporarily unavailable")


def is_transient_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(m in s for m in TRANSIENT_MARKERS)


def sleep_backoff(attempt: int, base: float = 0.5, cap: float = 8.0):
    # exp backoff with full jitter
    delay = min(cap, base * (2 ** (attempt - 1)))
    time.sleep(random.uniform(0, delay))


def make_retry_call(logger: LoggerInterface):
    def retry_call(fn: Callable[[], T], *, max_attempts: int = 3) -> T:
        attempt = 1
        while True:
            try:
                return fn()
            except Exception as e:
                if attempt >= max_attempts or not is_transient_error(e):
                    raise
                logger.warning(f"Transient error on attempt {attempt}: {e}")
                sleep_backoff(attempt)
                attempt += 1

    return retry_call


REPAIR_SYSTEM = "You will receive invalid JSON and a schema. Return STRICTLY valid JSON, exactly according to the schema. No comments, explanations, or formatting — only JSON."


def try_structured_once(messages, smart_llm, schema_model):
    return smart_llm.with_structured_output(schema_model, method="json_mode").invoke(
        messages
    )


def repair_json(smart_llm, broken_payload: str) -> dict:
    resp = smart_llm.invoke(
        [SystemMessage(content=REPAIR_SYSTEM), HumanMessage(content=broken_payload)]
    )
    return json.loads(str(resp.content))


def make_call_with_self_heal(logger: LoggerInterface):
    def call_with_self_heal(
        messages, smart_llm, schema_model, *, max_repairs: int = 3
    ):
        retry_call = make_retry_call(logger)
        try:
            return retry_call(
                lambda: try_structured_once(messages, smart_llm, schema_model),
            )
        except Exception as ve:
            last_err = ve

        repairs = 0
        user_json_str = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "{}"
        )
        while repairs < max_repairs:
            logger.warning(
                f"Invalid response according to the schema: {last_err}. Attempting repair #{repairs + 1}."
            )
            repaired = repair_json(
                smart_llm, f"Invalid response according to the schema:\n{user_json_str}"
            )
            logger.debug(f"Repaired JSON: {repaired}")
            try:
                return schema_model.model_validate(repaired)
            except Exception as ve:
                last_err = ve
                repairs += 1

        raise last_err

    return call_with_self_heal


def get_logger(name: str = __name__) -> LoggerInterface:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:  # Prevent duplicate handlers if called multiple times
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger  # Type: ignore[return-value]
