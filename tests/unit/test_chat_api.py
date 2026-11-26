import json

from droidpatch.api.deps import get_gateway
from droidpatch.llm.gateway import FakeLLM, LLMError, LLMGateway, Reply


def events(body: str) -> list[tuple[str, dict]]:
    """Parse a server-sent-event body into (event name, data) pairs."""
    out = []
    for block in body.strip().split("\n\n"):
        name = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                out.append((name, json.loads(line[5:])))
    return out


def test_chat_without_streaming_returns_json(client, llm):
    llm.script = ["docs", "Use curly braces in the path."]
    r = client.post(
        "/v1/chat", json={"message": "How do I declare a path parameter?", "stream": False}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Use curly braces in the path."
    assert body["provider"] == "fake" and body["tokens_out"] == 6 and "cost_inr" in body


def test_chat_streams_pieces_and_ends_with_a_done_event(client, llm):
    llm.script = ["docs", "Use curly braces in the path."]
    r = client.post("/v1/chat", json={"message": "How do I declare a path parameter?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    received = events(r.text)
    text = "".join(data["delta"] for name, data in received if name == "")
    assert text.strip() == "Use curly braces in the path."
    assert received[-1][0] == "done" and received[-1][1]["model"] == "fake-1"


def test_the_model_gets_the_system_prompt_from_the_prompt_file(client):
    assert "not sure" in client.app.state.system_prompt


def test_an_empty_message_is_a_422_problem(client):
    r = client.post("/v1/chat", json={"message": ""})
    assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"


def test_when_no_model_can_answer_the_api_says_503_not_200(client, llm):
    llm.script = [LLMError("HTTP 401: invalid API key", retryable=False)]
    r = client.post("/v1/chat", json={"message": "hello"})
    assert r.status_code == 503 and "No model could answer" in r.json()["detail"]


def test_a_failure_in_the_middle_of_a_stream_is_reported_as_an_error_event(client, llm):
    llm.script = ["docs", ("partial", LLMError("HTTP 503: overloaded", retryable=True))]
    r = client.post("/v1/chat", json={"message": "hello"})
    assert r.status_code == 200  # too late to change it: the first bytes were already sent
    assert events(r.text)[-1][0] == "error"


def test_usage_reports_tokens_and_rupees_per_day(client):
    r = client.get("/v1/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["days"][0]["tokens_in"] == 300 and body["total_cost_inr"] == 0.0642
    assert body["calls"] == 3


def test_llm_status_reports_closed_breaker_with_fakellm(client):
    r = client.get("/v1/llm/status")
    assert r.status_code == 200
    assert r.json() == {"providers": [{"name": "fake", "model": "fake-1", "state": "closed"}]}


def test_llm_status_walks_closed_open_and_half_open_with_fakellm(client):
    now = [100.0]
    failing = FakeLLM("gemini", "gemini-3.8-flash", [LLMError("HTTP 503", retryable=False)] * 3)
    backup = FakeLLM("groq", "openai/gpt-oss-20b", ["Backup answer."] * 5)
    gw = LLMGateway(
        [failing, backup],
        clock=lambda: now[0],
        breaker_threshold=3,
        breaker_cooldown=30.0,
    )
    previous = client.app.dependency_overrides.get(get_gateway)
    client.app.dependency_overrides[get_gateway] = lambda: gw
    try:
        assert client.get("/v1/llm/status").json()["providers"][0]["state"] == "closed"

        for _ in range(3):
            res = client.post("/v1/chat", json={"message": "check breaker", "stream": False})
            assert res.status_code == 200

        assert client.get("/v1/llm/status").json()["providers"][0]["state"] == "open"

        now[0] += 30.0
        assert client.get("/v1/llm/status").json()["providers"][0]["state"] == "half-open"
    finally:
        if previous is not None:
            client.app.dependency_overrides[get_gateway] = previous


def test_chat_sends_history_between_system_prompt_and_new_message(client):
    seen_messages: list[list[dict[str, str]]] = []

    class RecordingFakeLLM(FakeLLM):
        async def generate(self, messages, *, temperature=0.2, **options):
            seen_messages.append(messages)
            if len(seen_messages) == 1:
                return Reply("docs", tokens_in=10, tokens_out=1)
            return Reply("Pediatric guidance differs slightly.", tokens_in=45, tokens_out=5)

    gw = LLMGateway([RecordingFakeLLM("fake", "fake-1")])
    previous = client.app.dependency_overrides.get(get_gateway)
    client.app.dependency_overrides[get_gateway] = lambda: gw
    history = [
        {"role": "user", "content": "What is the patch level difference?"},
        {"role": "assistant", "content": "2024-05-01 covers OS; 2024-05-05 adds vendor fixes."},
    ]
    try:
        r = client.post(
            "/v1/chat",
            json={"message": "and for children?", "history": history, "stream": False},
        )
        assert r.status_code == 200
        assert r.json()["tokens_in"] == 45

        too_long = [{"role": "user", "content": f"msg {i}"} for i in range(7)]
        bad = client.post(
            "/v1/chat", json={"message": "next", "history": too_long, "stream": False}
        )
        assert bad.status_code == 422
    finally:
        if previous is not None:
            client.app.dependency_overrides[get_gateway] = previous

    sent = seen_messages[1]
    assert sent[0]["role"] == "system"
    assert sent[1:-1] == history
    assert sent[-1] == {"role": "user", "content": "and for children?"}
