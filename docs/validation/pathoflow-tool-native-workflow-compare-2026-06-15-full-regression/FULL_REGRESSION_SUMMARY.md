# Full Regression Summary

## Scope

- focused PathoFlow pytest regression
- tool-native workflow compare benchmark
- workflow contrast report
- DeepSeek live env probe
- DeepSeek general/task direct regression probe

## Result

- pytest: `190 passed, 1 skipped`
- tool-native compare: completed
- contrast report: completed
- DeepSeek env override probe: completed
- DeepSeek direct regression probe: completed

## Key Conclusions

- `general` is confirmed to be a free-text contract branch, not a crash path
- `general` now returns `_free_text_response=true` and no longer surfaces a fake `_parse_error`
- `task_planning` structured output for `deepseek-v4-pro` remains parseable after the token-budget and parser fixes
- no regression was observed in the previously fixed PathoFlow planner / overlay / Macenko / reviewed-TME reduced-chain areas inside the covered test and benchmark scope

## Key Files

- `pathoflow-tool-native-workflow-compare-2026-06-15/README.md`
- `pathoflow-tool-native-workflow-compare-2026-06-15/workflow_contrast_report.md`
- `env_override_probe.json`
- `deepseek_full_regression_probe.json`
