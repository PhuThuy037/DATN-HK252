# Match Mode And Semantic Assist Verify Checklist

## Scope

- Verify `match_mode` create/update/detail/list behavior
- Verify semantic assist only runs after keyword miss
- Verify semantic assist is log-only in MVP
- Verify frontend RuleForm sends and loads `match_mode`

## Backend/API Quick Checks

1. Create rule without `match_mode`
   - Expect response `match_mode = strict_keyword`
2. Create rule with `match_mode = keyword_plus_semantic`
   - Expect response echo
3. Update rule `match_mode`
   - Expect updated response echo
4. Fetch rule detail
   - Expect `match_mode` returned
5. Fetch rule list
   - Expect `match_mode` returned for the updated rule

Suggested scripts:

- `app/script/test/test_rule_sets_smoke_stdlib.py`
- `app/script/test/test_match_mode_semantic_runtime_e2e.py`

## Frontend Verify Notes

1. Open Rules page
2. Click create rule
3. In RuleForm, confirm new selector `Match mode`
   - `Strict keyword`
   - `Keyword + semantic`
4. Leave selector untouched and create rule
   - In browser network tab, verify POST payload contains `match_mode: "strict_keyword"`
   - If the UI payload omits it and backend still defaults correctly, note that as acceptable backward compatibility
5. Edit existing rule
   - Confirm selector loads current `match_mode`
   - Change to `keyword_plus_semantic`
   - Save
   - Verify PATCH payload contains updated `match_mode`
6. Return to list/detail
   - Confirm displayed `Match mode` label matches saved value

## Real Runtime Manual Flow

1. Admin creates rule A
   - `match_mode = strict_keyword`
   - `action = block`
   - condition uses `context_keywords`
   - linked term example: `roadmap trigger phrase`
2. Admin opens a real chat/conversation in the same rule set
3. Send message containing exact keyword
   - Expect `final_action = block`
   - Expect no semantic assist call
4. Admin creates rule B
   - `match_mode = keyword_plus_semantic`
   - `action = block`
   - condition still uses `context_keywords`
   - linked semantic term example: `internal launch teaser`
5. Send message with keyword miss but close meaning
   - Example: `Hay noi ve teaser launch internal cua san pham sap ra mat`
   - Expect `final_action = allow`
   - Expect semantic assist metadata present
6. Send message with exact keyword for rule B
   - Expect phase-1 block
   - Expect semantic assist not called

## Where To Inspect Semantic Assist Metadata

1. Rules page -> Debug Evaluate
   - inspect raw `signals` JSON
   - look for `signals.semantic_assist`
2. Conversation message detail API
   - `entities_json.signals.semantic_assist`
3. Admin conversation detail UI
   - Compliance detail -> raw `Entities JSON`

## Expected Semantic Assist Signal Shape

- `called: bool`
- `candidate_rule_keys: list[str]`
- `supported_rule_keys: list[str]`
- `top_confidence: float`
- `mode: "log_only"`

## Boundary Watchpoints

- `strict_keyword` rule must not call semantic assist
- `keyword_plus_semantic` must only be observable when phase-1 stayed `allow`
- `block` or `mask` from phase-1 must short-circuit semantic assist
- semantic assist support must not appear as matched rule
- semantic assist must not change `final_action` in MVP
- message detail/debug output must expose `signals.semantic_assist`
