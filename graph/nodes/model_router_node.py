# graph/nodes/model_router_node.py

def select_model(prompt: str):

    word_count = len(prompt.split())

    # Low-code heuristic routing
    if word_count < 25:
        return "gpt-4o-mini"

    if word_count < 80:
        return "gpt-4o-mini"

    return "gpt-4o"


async def model_router_node(state: dict):

    prompt = state["prompt"]

    model = select_model(prompt)

    state["model_used"] = model

    state["policy_decisions"].append({
        "node": "model_router",
        "rule": "MODEL_SELECTION",
        "action": model
    })

    print(f"[Model Router] Selected model: {model}")

    return state