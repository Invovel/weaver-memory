# Control Plus N Models: Long-Term Memory Experiment Protocol

## Research Question

Does MemoryWeaver improve answer quality and retrieval reliability over time
without unacceptable latency, cost, or pollution?

Three models are enough for a pilot. The protocol uses `N` models so later
models can be added without changing the design.

## Experimental Factors

Treat model choice and memory strategy as separate factors.

| Factor | Levels |
| --- | --- |
| Model | `M1 ... Mn` |
| Memory condition | `C0`, `C1`, `C2`, `C3` |
| Dataset | LongMemEval cleaned, LoCoMo-MC10, MIRACL-zh subset, later SciFact and HAGRID |
| Time checkpoint | `T0`, `T1`, `T2`, ..., `Tk` |
| Repetition | fixed seed set, at least `5` pilot repeats and preferably `10+` confirmatory repeats |

### Memory conditions

| ID | Condition | Purpose |
| --- | --- | --- |
| `C0` | No persistent memory | Control group |
| `C1` | Cold-start MemoryWeaver, online accumulation | Measures learning curve |
| `C2` | Long-running MemoryWeaver at checkpoints | Measures drift, speed, and pollution over time |
| `C3` | Direct import of specification-compliant processed memory | Compares curated initialization against cold start |

Optional ablations can be added later:

| ID | Ablation |
| --- | --- |
| `A1` | Retrieval without source gate |
| `A2` | Retrieval without graph expansion |
| `A3` | Retrieval without reranking |
| `A4` | Retrieval without checkpoint recovery |

Do not mix ablations into the main control comparison until P0 gates are
stable. Unsafe ablations should run only in an isolated offline harness.

## Primary Metrics

### Correctness

| Metric | Meaning |
| --- | --- |
| Accuracy / exact match / F1 | Task-level correctness |
| Recall@k | Whether relevant evidence was retrieved |
| MRR and nDCG@k | Retrieval ranking quality |
| Citation precision and recall | Evidence attribution quality |
| Unsupported-claim rate | Answers without supporting evidence |
| Pollution leakage rate | Unverified assistant or synthetic memory returned as verified |
| Fast-path false-positive rate | Incorrectly routed fast decisions |

### Reproducibility

| Metric | Meaning |
| --- | --- |
| Repeat agreement | Fraction of repeated runs producing the same outcome |
| Accuracy standard deviation | Variation across seeds or repetitions |
| Retrieval-set Jaccard | Stability of retrieved evidence |
| Route agreement | Stability of `thinking`, `fast_verify`, and `fast` decisions |
| Failure recurrence rate | Whether the same bad case can be reproduced |

### Speed And Resource Use

| Metric | Meaning |
| --- | --- |
| Single-turn latency p50 / p95 / p99 | Cold and warm response latency |
| Multi-turn latency curve | Latency as history grows |
| Retrieval latency p50 / p95 / p99 | Memory lookup cost |
| Ingest throughput | Imported or online memories per second |
| Token count and model-call count | Cost driver |
| Wall-clock cost per successful answer | Efficiency |
| Store size and RSS | Long-run capacity signal |

### Longitudinal Health

| Metric | Meaning |
| --- | --- |
| Accuracy by checkpoint | Learning or degradation over time |
| Latency slope | Cost of growing memory |
| Promotion and demotion rate | Memory lifecycle health |
| Conflict rate | Contradictory-memory pressure |
| Zero-result rate | Retrieval miss pressure |
| Stale-memory hit rate | Outdated-memory exposure |
| Duplicate-memory rate | Compaction need |
| Recovery success and duplicate side effect rate | Durable execution quality |

## Statistical Analysis

Use paired comparisons because each model-condition pair should receive the
same example order and seed set.

| Question | Recommended analysis |
| --- | --- |
| Does memory improve accuracy? | Paired bootstrap confidence interval and paired permutation test or Wilcoxon signed-rank test |
| Does latency change? | Compare p50 / p95 / p99 and fit a checkpoint latency slope |
| Does quality drift over time? | Mixed-effects model with model, condition, and checkpoint as factors |
| Are repeated runs stable? | Agreement rate, standard deviation, and retrieval-set Jaccard |
| Are many hypotheses tested? | Benjamini-Hochberg false-discovery-rate correction |
| Is the effect practically meaningful? | Report effect size and confidence interval, not only p-value |

For every metric, report:

```text
n
mean
median
standard deviation
95% confidence interval
paired delta versus C0
effect size
raw sample reference
```

## Visualizations

| Figure | Axes | Purpose |
| --- | --- | --- |
| Volcano plot | x: paired effect size, y: `-log10(q-value)` | Highlights improvements and regressions with statistical support |
| Learning curve | x: checkpoint or turns, y: accuracy / Recall@k | Shows cold start versus long-running behavior |
| Latency curve | x: checkpoint or memory size, y: p50 / p95 / p99 latency | Shows scaling cost |
| Box or violin plot | x: condition, y: latency or accuracy | Shows distribution, not only averages |
| Reproducibility heatmap | rows: models, columns: conditions, color: agreement | Shows stability |
| Pareto frontier | x: latency or cost, y: accuracy | Shows useful trade-offs |
| Pollution dashboard | x: checkpoint, y: leakage / conflict / stale-hit rate | Shows long-term safety |

Create separate volcano plots for accuracy, retrieval quality, and latency.
Do not mix metrics with different meanings on one x-axis.

## Execution Procedure

1. Freeze the protocol, model identifiers, prompt template, tool policy, and
   scoring code.
2. Pin dataset Hub revisions, licenses, splits, sample policies, and hashes.
3. Build adapters that preserve provenance and mark generated text as
   `source=synthetic`.
4. Run a small pilot with three models and at least five repeats.
5. Estimate variance and run a power analysis for the confirmatory batch.
6. Randomize example order and block runs by model and memory condition.
7. Execute `C0` through `C3` at the same checkpoints with the same seed set.
8. Persist raw prompts, responses, retrieved memory IDs, citations, routes,
   latency, token counts, errors, and environment metadata.
9. Validate the run manifest before calculating summary statistics.
10. Calculate paired deltas, confidence intervals, adjusted q-values, and
    effect sizes.
11. Render the figure set and review bad cases manually.
12. Archive raw data, processed data, reports, code revision, and a Git tag.

## Minimum Pilot Matrix

For the current three models:

```text
3 models
x 4 memory conditions
x 5 repeats
x fixed development sample
= 60 run cells
```

The pilot is for variance estimation and pipeline verification. It is not yet
a definitive model ranking.
