from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from nanobody_agent.config import get_settings
from nanobody_agent.nodes import (
    GraphDeps,
    classify_router,
    direct_llm_answer,
    generate_answer,
    llm_router,
    nanokgat_predict,
    reject_low_relevance,
    run_domain_tools,
    retrieve_knowledge,
    route_after_classify_factory,
    route_after_llm_router,
)
from nanobody_agent.retrieval import HybridRetriever
from nanobody_agent.state import AgentState


def build_app():
    settings = get_settings()
    retriever = HybridRetriever(settings)
    retriever.load_corpus()
    deps = GraphDeps(settings=settings, retriever=retriever)

    g = StateGraph(AgentState)
    g.add_node("classify_router", partial(classify_router, deps=deps))
    g.add_node("retrieve_knowledge", partial(retrieve_knowledge, deps=deps))
    g.add_node("generate_answer", partial(generate_answer, deps=deps))
    g.add_node("llm_router", partial(llm_router, deps=deps))
    g.add_node("direct_llm_answer", partial(direct_llm_answer, deps=deps))
    g.add_node("nanokgat_predict", partial(nanokgat_predict, deps=deps))
    g.add_node("run_domain_tools", partial(run_domain_tools, deps=deps))
    g.add_node("reject_low_relevance", partial(reject_low_relevance, deps=deps))

    g.add_edge(START, "classify_router")
    g.add_conditional_edges(
        "classify_router",
        route_after_classify_factory(settings.kb_relevance_threshold),
        {
            "kb": "retrieve_knowledge",
            "llm": "llm_router",
            "reject": "reject_low_relevance",
        },
    )
    g.add_edge("retrieve_knowledge", "generate_answer")
    g.add_edge("generate_answer", END)

    g.add_conditional_edges(
        "llm_router",
        route_after_llm_router,
        {
            "direct": "direct_llm_answer",
            "pred": "nanokgat_predict",
            "viz": "nanokgat_predict",
            "tools": "run_domain_tools",
        },
    )
    g.add_edge("direct_llm_answer", END)
    g.add_edge("nanokgat_predict", END)
    g.add_edge("run_domain_tools", END)
    g.add_edge("reject_low_relevance", END)

    return g.compile()
