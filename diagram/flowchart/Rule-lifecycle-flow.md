::: mermaid
flowchart TD
CreateRule["Create Rule API"] --> ValidateCreate["Validate permission + payload"];
ValidateCreate --> SaveRule["Save Rule in DB"];
SaveRule --> UpsertEmbedding["Upsert Rule Embedding"];
UpsertEmbedding --> InvalidateCache["Invalidate RuleEngine cache"];
InvalidateCache --> ActivateRule["Rule becomes effective"];

UpdateRule["Update Rule API"] --> ValidateUpdate["Validate version + payload"];
ValidateUpdate --> SaveRule;

ToggleRule["Toggle enabled / global override"] --> SaveOverride["Save company/user override"];
SaveOverride --> InvalidateCache;
SaveOverride --> ActivateRule;

DeleteRule["Delete Rule API"] --> DeactivateRule["Soft delete or disable rule"];
DeactivateRule --> SaveRule;
DeactivateRule --> InvalidateCache;
DeactivateRule --> RemovedFromRuntime["Removed from effective runtime set"];

ActivateRule --> RuntimeUsage["RuleEngine.load_rules (layering + override)"];
RuntimeUsage --> ChatFlow["Used by Chat runtime scan"];
RuntimeUsage --> DebugEvaluate["Used by Debug evaluate/full-scan"];
RuntimeUsage --> SuggestionSimulate["Used by Suggestion simulate"];
:::
