from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
PWD = os.getenv("TEST_USER_PASSWORD", "123456")


def fail(msg: str) -> None:
    raise AssertionError(msg)


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json",
    }


def register_and_login_fresh_user(client: httpx.Client) -> str:
    now = int(time.time())
    email = f"match.mode.semantic.{now}@test.com"
    name = f"Match Mode Semantic {now}"

    r = client.post(
        f"{V1}/auth/register",
        json={"email": email, "password": PWD, "name": name},
    )
    if r.status_code not in (200, 201, 409):
        fail(f"register failed: HTTP {r.status_code}\n{r.text}")

    r = client.post(
        f"{V1}/auth/login",
        json={"email": email, "password": PWD},
    )
    if r.status_code != 200:
        fail(f"login failed: HTTP {r.status_code}\n{r.text}")
    token = str((r.json().get("data") or {}).get("access_token") or "").strip()
    if not token:
        fail("missing access_token")
    return token


def create_rule_set(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/rule-sets",
        json={"name": f"Match Mode Runtime {int(time.time())}"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    rule_set_id = str((r.json().get("data") or {}).get("id") or "").strip()
    if not rule_set_id:
        fail("missing rule_set_id")
    return rule_set_id


def create_rule(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        json=payload,
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create rule failed: HTTP {r.status_code}\n{r.text}")
    data = r.json().get("data") or {}
    if not str(data.get("id") or "").strip():
        fail(f"missing created rule id: {data}")
    return data


def create_rule_set_conversation(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
) -> str:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/conversations",
        json={"title": f"match-mode-conv-{int(time.time())}"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create conversation failed: HTTP {r.status_code}\n{r.text}")
    data = r.json().get("data") or {}
    conversation_id = str(data.get("id") or "").strip()
    if not conversation_id:
        fail(f"missing conversation id: {data}")
    return conversation_id


def send_message(
    client: httpx.Client,
    token: str,
    conversation_id: str,
    content: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/conversations/{conversation_id}/messages",
        json={"content": content, "input_type": "user_input"},
        headers=auth_headers(token),
    )
    if r.status_code not in (200,):
        fail(f"send message failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def get_message_detail(
    client: httpx.Client,
    token: str,
    conversation_id: str,
    message_id: str,
) -> dict[str, Any]:
    r = client.get(
        f"{V1}/conversations/{conversation_id}/messages/{message_id}",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"get message detail failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def _semantic_signal(message_detail: dict[str, Any]) -> dict[str, Any]:
    entities_json = dict(message_detail.get("entities_json") or {})
    signals = dict(entities_json.get("signals") or {})
    return dict(signals.get("semantic_assist") or {})


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/8] register/login fresh user and create rule set")
        token = register_and_login_fresh_user(client)
        rule_set_id = create_rule_set(client, token)

        keyword_term = "roadmap trigger phrase"
        print("[2/8] create strict_keyword rule and verify explicit match_mode")
        strict_rule = create_rule(
            client,
            token,
            rule_set_id,
            {
                "rule": {
                    "stable_key": f"match.mode.strict.{int(time.time())}",
                    "name": "Strict roadmap guard",
                    "description": "Block exact roadmap trigger phrase",
                    "scope": "chat",
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": [keyword_term],
                                }
                            }
                        ]
                    },
                    "action": "block",
                    "severity": "high",
                    "priority": 220,
                    "match_mode": "strict_keyword",
                    "rag_mode": "off",
                    "enabled": True,
                },
                "context_terms": [
                    {
                        "entity_type": "CUSTOM_SECRET",
                        "term": keyword_term,
                        "lang": "vi",
                        "weight": 1,
                        "window_1": 60,
                        "window_2": 20,
                        "enabled": True,
                    }
                ],
            },
        )
        if str(strict_rule.get("match_mode") or "") != "strict_keyword":
            fail(f"strict rule match_mode mismatch: {strict_rule}")

        strict_conversation_id = create_rule_set_conversation(client, token, rule_set_id)

        print("[3/8] strict_keyword exact hit should block without semantic assist")
        strict_send = send_message(
            client,
            token,
            strict_conversation_id,
            f"Vui long viet ve {keyword_term}",
        )
        strict_message_id = str(strict_send.get("id") or "").strip()
        if str(strict_send.get("final_action") or "").lower() != "block":
            fail(f"strict exact hit must block: {strict_send}")
        strict_detail = get_message_detail(
            client,
            token,
            strict_conversation_id,
            strict_message_id,
        )
        strict_semantic = _semantic_signal(strict_detail)
        if strict_semantic.get("called") is not False:
            fail(f"strict rule should not call semantic assist: {strict_semantic}")

        print("[4/8] create keyword_plus_semantic rule")
        semantic_rule = create_rule(
            client,
            token,
            rule_set_id,
            {
                "rule": {
                    "stable_key": f"match.mode.semantic.{int(time.time())}",
                    "name": "Internal Launch Teaser",
                    "description": "Sensitive internal launch teaser for unreleased product",
                    "scope": "chat",
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": [keyword_term],
                                }
                            }
                        ]
                    },
                    "action": "block",
                    "severity": "high",
                    "priority": 180,
                    "match_mode": "keyword_plus_semantic",
                    "rag_mode": "off",
                    "enabled": True,
                },
                "context_terms": [
                    {
                        "entity_type": "SEM_TOPIC",
                        "term": "internal launch teaser",
                        "lang": "vi",
                        "weight": 1,
                        "window_1": 60,
                        "window_2": 20,
                        "enabled": True,
                    }
                ],
            },
        )
        if str(semantic_rule.get("match_mode") or "") != "keyword_plus_semantic":
            fail(f"semantic rule match_mode mismatch: {semantic_rule}")

        semantic_conversation_id = create_rule_set_conversation(client, token, rule_set_id)

        print("[5/8] keyword_plus_semantic target-only hit should stay allow")
        exact_send = send_message(
            client,
            token,
            semantic_conversation_id,
            f"Toi muon noi ve {keyword_term}",
        )
        exact_message_id = str(exact_send.get("id") or "").strip()
        if str(exact_send.get("final_action") or "").lower() != "allow":
            fail(f"semantic rule target-only hit must stay allow: {exact_send}")
        exact_detail = get_message_detail(
            client,
            token,
            semantic_conversation_id,
            exact_message_id,
        )
        exact_semantic = _semantic_signal(exact_detail)
        if exact_semantic.get("called") is not True:
            fail(f"semantic assist should run when target matches without topic support: {exact_semantic}")

        print("[6/8] keyword_plus_semantic target + topic exact hit should block via phase-1")
        exact_topic_send = send_message(
            client,
            token,
            semantic_conversation_id,
            f"Toi muon noi ve {keyword_term} internal launch teaser",
        )
        exact_topic_message_id = str(exact_topic_send.get("id") or "").strip()
        if str(exact_topic_send.get("final_action") or "").lower() != "block":
            fail(f"semantic rule target+topic exact hit must block: {exact_topic_send}")
        exact_topic_detail = get_message_detail(
            client,
            token,
            semantic_conversation_id,
            exact_topic_message_id,
        )
        exact_topic_semantic = _semantic_signal(exact_topic_detail)
        if exact_topic_semantic.get("called") is not False:
            fail(f"semantic assist must not run after phase-1 target+topic block: {exact_topic_semantic}")

        print("[7/8] keyword miss but near meaning should allow and log semantic assist")
        near_send = send_message(
            client,
            token,
            semantic_conversation_id,
            "Hay noi ve teaser launch internal cua san pham sap ra mat",
        )
        near_message_id = str(near_send.get("id") or "").strip()
        if str(near_send.get("final_action") or "").lower() != "allow":
            fail(f"semantic assist MVP must not change final_action: {near_send}")
        near_detail = get_message_detail(
            client,
            token,
            semantic_conversation_id,
            near_message_id,
        )
        near_semantic = _semantic_signal(near_detail)
        if near_semantic.get("called") is not True:
            fail(f"semantic assist should run on keyword miss with eligible rule: {near_semantic}")
        candidate_keys = [str(x) for x in list(near_semantic.get("candidate_rule_keys") or [])]
        if str(semantic_rule.get("stable_key") or "") not in candidate_keys:
            fail(f"semantic candidate keys should include semantic rule: {near_semantic}")
        supported_keys = [str(x) for x in list(near_semantic.get("supported_rule_keys") or [])]
        if str(semantic_rule.get("stable_key") or "") not in supported_keys:
            fail(f"semantic supported keys should include semantic rule: {near_semantic}")
        if float(near_semantic.get("top_confidence") or 0.0) <= 0.0:
            fail(f"semantic top_confidence should be positive: {near_semantic}")
        if str(near_semantic.get("mode") or "") != "log_only":
            fail(f"semantic mode should be log_only: {near_semantic}")

        print("[8/8] verify metadata is exposed through message detail entities_json.signals")
        if not isinstance((near_detail.get("entities_json") or {}).get("signals"), dict):
            fail(f"message detail should expose signals metadata: {near_detail}")

        print("[9/9] verify semantic assist does not masquerade as matched rule")
        matched_rule_ids = [str(x) for x in list(near_detail.get("matched_rule_ids") or []) if str(x)]
        if str(semantic_rule.get("id") or "") in matched_rule_ids:
            fail(
                "semantic assist MVP must not turn support into matched rule/final action: "
                f"{near_detail}"
            )

    print("ALL PASS: match_mode + semantic assist runtime works on real rule create + chat flow.")


if __name__ == "__main__":
    main()
