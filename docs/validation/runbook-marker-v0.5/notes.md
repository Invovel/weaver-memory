# Runbook Marker v0.5 Notes

This fixture validates the trace contract, not end-to-end task success. Counterfactuals are manual annotations with confidence values, not measured trajectory reductions.

The five golden cards cover:

1. Codex subscription failed: full trace chain and known bad path suppression.
2. npm install dependency conflict: two guard markers hit and conflict is logged.
3. Docker build warning: weak signal retained as partial evidence.
4. CI test timeout: freshness conflict between old terminal and newer tool output.
5. API key exists but rejected: ambiguous evidence must not become positive auth memory.
