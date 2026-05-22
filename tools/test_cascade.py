"""test_cascade.py - Verifica que el Cascading Fallback funciona.

Simula:
  1. openrouter responde OK las primeras 5 veces
  2. en la 6ta devuelve 402 Payment Required
  3. cascada activa: ask_claude debe automaticamente probar anthropic_proxy
  4. proxy funciona en las siguientes
  5. assert: las 20 llamadas devuelven texto (no None)

Sin mocks externos. Usa monkeypatch sobre _ask_openrouter para forzar 402.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import jarvis_bridge.jarvis_brain as B

    # Counters
    state = {"or_calls": 0, "proxy_calls": 0}

    original_or = B._ask_openrouter
    original_proxy_call = B.requests.post

    def fake_openrouter(prompt, system, max_tokens, timeout):
        state["or_calls"] += 1
        if state["or_calls"] <= 5:
            return f"[openrouter#{state['or_calls']}] OK reply"
        # 6ta llamada y siguientes: simular 402 sobregirado
        raise requests_402_exception()

    class _Resp402:
        status_code = 402
        text = '{"error":{"message":"Payment Required","code":402}}'
        def raise_for_status(self):
            from requests import HTTPError, Response
            r = Response()
            r.status_code = 402
            raise HTTPError("402 Client Error: Payment Required", response=r)

    def requests_402_exception():
        from requests import HTTPError, Response
        r = Response()
        r.status_code = 402
        return HTTPError("402 Client Error: Payment Required for url: openrouter",
                          response=r)

    # Mock proxy call: cualquier POST a 127.0.0.1:8088 devuelve OK
    def fake_post(url, *args, **kwargs):
        if "127.0.0.1:8088" in url or "/v1/messages" in url:
            state["proxy_calls"] += 1
            class _ROK:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self):
                    return {"content": [{"text": f"[proxy#{state['proxy_calls']}] OK reply"}]}
            return _ROK()
        # Real para otros (health checks)
        return original_proxy_call(url, *args, **kwargs)

    # Patch
    B._ask_openrouter = fake_openrouter
    B.requests.post = fake_post
    # Force chain: openrouter primary, anthropic_proxy en fallback
    B.LLM_PROVIDER = "openrouter"
    B.LLM_FALLBACK = ["anthropic_proxy"]
    B.OPENROUTER_API_KEY = "dummy"
    # Stub proxy_healthy para que no haga health real
    B._proxy_healthy = lambda timeout=3.0: True

    print("=== test_cascade: 20 calls openrouter (5 OK, luego 402 -> proxy) ===")
    failures = []
    for i in range(1, 21):
        r = B.ask_claude(f"prompt #{i}", retries=0, timeout=5)
        if not r:
            failures.append((i, "ask_claude returned None"))
            print(f"  [{i:2}] FAIL: returned None")
        else:
            via = "OR" if r.startswith("[openrouter") else ("PROXY" if r.startswith("[proxy") else "?")
            print(f"  [{i:2}] OK via {via}: {r[:50]}")

    # Restore
    B._ask_openrouter = original_or
    B.requests.post = original_proxy_call

    print()
    print(f"openrouter calls: {state['or_calls']} (5 OK + 15 fatal 402)")
    print(f"anthropic_proxy calls: {state['proxy_calls']} (15 takeovers)")
    print(f"failures: {len(failures)}")

    # Asserts
    assert len(failures) == 0, f"Hubo {len(failures)} fails: {failures[:3]}"
    assert state["or_calls"] >= 20, f"openrouter debio invocarse 20 veces, fue {state['or_calls']}"
    assert state["proxy_calls"] >= 15, f"proxy fallback debio activarse 15 veces, fue {state['proxy_calls']}"
    print("\nPASS: Cascading Fallback OK end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
