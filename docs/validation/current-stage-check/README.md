# Current Stage Check

This directory is the fixed daily review workspace for the current repository stage.

Run:

```powershell
python .\scripts\current_stage_check.py --tidy-root
```

What it does:

1. Archives transient root-level `.memoryweaver-*` and `.tmp-*` folders into `.workspace_runs/`.
2. Runs `pytest`, the local prototype baseline, `mw layer smoke`, `mw validate`, `mw doctor`, and `mw eval tau-smoke`.
3. Compares today's measured prototype benchmark with the hard-coded benchmark tables in `README.md` and `README_ZH.md`.
4. Writes a stage report with:
   - today's TODO snapshot
   - the current implementation stage
   - README / docs claim differences
   - concrete next suggestions

Generated files:

- `pytest.txt`
- `prototype_baseline.json`
- `layer_smoke.json`
- `validate_layer.json`
- `doctor_layer.json`
- `tau_smoke.json`
- `report.json`
- `report.md`

This check is intentionally focused on the current v0.7 path-promotion closure story instead of broader future-system claims.
