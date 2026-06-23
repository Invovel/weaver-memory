# Benchmark Sequential Chain Recheck

## Conclusion

This was not a real model-sample fluctuation.
It was a benchmark harness pathing issue in the sequential overlay chains.

## What Happened

In the `full-regression` package, these two chains showed `success_count=1, failure_count=1`:

- `tool_executor_foreground_overlay`
- `tool_executor_nucleus_overlay`

The concrete failure was:

- `59-generate-overlays` received a staged fake slide path like `..._staged\demo_*_foreground.svs`
- that temporary placeholder path was reported missing
- the failure therefore came from benchmark input construction, not from PathoFlow planner drift or sample-level instability

## Root Cause

`benchmarks/pathoflow_tool_native_workflow_compare.py` used a synthetic empty `.svs` stub for sequential overlay chains instead of reusing the chain's original source slide.

That makes the benchmark more fragile than the actual demo overlay execution path.

## Verification

After changing the sequential chain benchmark to reuse `source_slide_paths` for overlay execution when available, a direct recheck returned:

- `tool_executor_foreground_overlay 2 0 0`
- `tool_executor_nucleus_overlay 2 0 0`
- `tool_executor_detection_overlay 2 0 0`
- `tool_executor_macenko_detection 2 0 0`

## Interpretation

So the earlier `1/1/0` result should be classified as a benchmark harness artifact, not as evidence of true sample fluctuation or execution instability in the underlying demo chain.
