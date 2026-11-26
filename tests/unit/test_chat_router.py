"""Router behavior in /v1/chat tested with FakeLLM."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from droidpatch.api.deps import get_gateway
from droidpatch.api.routes.chat import FIXED_REPLIES, router
from droidpatch.llm.gateway import FakeLLM, LLMGateway


def make_client(llm: FakeLLM) -> TestClient:
    app = FastAPI()
    app.state.system_prompt = "Answer using only the provided Android security bulletins."
    app.include_router(router, prefix="/v1")
    gateway = LLMGateway([llm])
    app.dependency_overrides[get_gateway] = lambda: gateway
    return TestClient(app)


def test_question_6_personal_stops_after_one_call():
    llm = FakeLLM(script=["personal", "500 phones updated today."])
    client = make_client(llm)

    resp = client.post(
        "/v1/chat",
        json={
            "message": "Which of our 500 phones installed the latest update today?",
            "stream": False,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["answer"] == FIXED_REPLIES["personal"]
    assert "I can't know that" in resp.json()["answer"]
    assert llm.calls == 1


def test_off_topic_stops_after_one_call_and_docs_makes_second_call():
    off_llm = FakeLLM(script=["off_topic", "A dog name."])
    off_resp = make_client(off_llm).post(
        "/v1/chat",
        json={"message": "Suggest a name for my pet dog.", "stream": False},
    )
    assert off_resp.status_code == 200
    assert off_resp.json()["answer"] == FIXED_REPLIES["off_topic"]
    assert off_llm.calls == 1

    docs_llm = FakeLLM(script=["docs", "Fixed in the March 2025 bulletin."])
    docs_resp = make_client(docs_llm).post(
        "/v1/chat",
        json={
            "message": (
                "Which Critical vulnerabilities in the System component were fixed "
                "in the March 2025 bulletin?"
            ),
            "stream": False,
        },
    )
    assert docs_resp.status_code == 200
    assert docs_resp.json()["answer"] == "Fixed in the March 2025 bulletin."
    assert docs_llm.calls == 2
