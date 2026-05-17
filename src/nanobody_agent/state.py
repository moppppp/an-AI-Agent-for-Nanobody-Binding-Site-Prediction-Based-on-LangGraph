from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Intent = Literal["definition", "comparison", "prediction", "visualization", "unknown"]


class AgentState(TypedDict, total=False):
    """图状态：用户问题、检索、意图与最终输出。"""

    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    memory_context: str
    conversation_summary: str
    extended_retrieval: bool
    reject: bool
    pdb_path: str
    pdb_meta: dict

    relevance: float
    relevance_detail: dict
    semantic_verify_score: float | None
    route_kb: bool
    knowledge_snippets: list[str]

    intent: Intent
    intent_raw: str

    route_name: str
    reject_reason: str

    citations: list[dict]
    final_answer: str
    prediction_payload: dict
    pymol_link: str
