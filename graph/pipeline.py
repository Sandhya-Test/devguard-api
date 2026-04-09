from graph.builder import build_graph


_PIPELINE = build_graph()


async def run_pipeline(state: dict):
    return await _PIPELINE.ainvoke(state)
