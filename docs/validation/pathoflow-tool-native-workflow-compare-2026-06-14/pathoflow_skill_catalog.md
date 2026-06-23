# PathoFlow Skill Catalog

## Purpose

This is Stage 3 of the PathoFlow native-framework investigation.

The goal is not to make PathoFlow look more complete than it is. The goal is
to compress the currently known model families, reviewed registry flows, and
tool-native execution evidence into a small set of reusable skills that can be
scheduled deterministically.

Each skill below records:

- what the skill is for,
- which PathoFlow tools or reviewed flows it depends on,
- what it expects as input,
- what it should emit,
- whether it is currently usable,
- and where it breaks in the present repository.

## Readiness Levels

- `ready`
  The core path has local execution evidence and produces usable artifacts.
- `partial`
  At least one main step is locally validated, but an important downstream step
  is blocked, missing, or contract-fragile.
- `declared_only`
  The skill is clearly represented in the reviewed registry, but was not
  locally executed in this pass.
- `blocked`
  The intended chain is currently non-usable because a critical stage emits no
  artifacts or fails contract handoff.

## Skill 1: Slide Preprocess Gate

Skill ID: `skill_preprocess_qc_mask`

Purpose:

- filter obviously bad slides,
- estimate spacing when it is unknown,
- restrict downstream analysis to valid tissue.

PathoFlow blocks:

- `40-GrandQC`
- `57-estimate-image-spacing`
- `1-foreground-segmentation`

Recommended sequence:

`40-GrandQC? -> 57-estimate-image-spacing? -> 1-foreground-segmentation`

Input contract:

- `input_slide`
  or `input_images` in the spacing-estimation special case

Expected output contract:

- `qc_report_json` or `qc_label`
- optional `resolution_value`
- `foreground_mask`

Current readiness:

- `partial`

Why:

- `1-foreground-segmentation` is locally verified and emits a real mask file.
- `40` and `57` are registry-declared and semantically correct, but they were
  not locally executed in this pass.

Known breakpoints:

- Planner drift can skip or misroute this skill if selection is not
  deterministic.

When to use:

- before classification,
- before region segmentation,
- before nucleus/pathomics,
- before expensive external tasks.

When not to use:

- when the task already starts from trusted mask artifacts,
- when the task is pure modality generation and tissue restriction is not
  needed.

## Skill 2: Classification Screening

Skill ID: `skill_classification_screening`

Purpose:

- run disease-specific or pan-cancer screening at the slide level,
- emit heatmaps, suspicious-region reports, and coarse masks.

PathoFlow blocks:

- preprocess gate:
  `skill_preprocess_qc_mask`
- detection core:
  `5-pancreas-tumor-detection`
  `6-breast-tumor-detection`
  `62-pancancer-detection-20`
  `63-pancancer-detection-40`
- visualization:
  `59-generate-overlays`

Recommended sequence:

`skill_preprocess_qc_mask -> 5|6|62|63 -> 59?`

Input contract:

- `input_slide`

Expected output contract:

- `heatmap_tif` or equivalent detection image
- `tumor_mask`
- `score_json`
- optional overlay

Current readiness:

- `partial`

Why:

- `5` and `6` are locally validated in `cpu_pseudo` mode and produce image,
  mask, and report artifacts.
- the overlay tail is not composable yet because local detection masks are PNG
  while overlay expects TIF/TIFF.

Known breakpoints:

- `classification -> overlay` format mismatch
- planner drift across disease families

Auto-scheduling policy:

- do not let current `OfflineFlowPlanner` choose the disease model freely
- require deterministic disease/task constraints first

## Skill 3: Region Segmentation

Skill ID: `skill_region_segmentation`

Purpose:

- produce WSI-aligned tissue or lesion masks for downstream interpretation or
  mask-based pipelines.

PathoFlow blocks:

- preprocess gate:
  `skill_preprocess_qc_mask`
- segmentation core:
  `2-lung-cancer-segmentation`
  `11-CD34-vessel-segmentation`
  `12-PAS-kidney-glomeruli-segmentation`
  `16-liver-tissue-segmentation`
  `17-lung-tertiary-lymphoid-structures-segmentation`
  `18-PAS-kidney-glomeruli-multi-class-segmentation`
  `26-Kidney-Masson-4-class-segmentation`
- visualization:
  `59-generate-overlays`

Recommended sequence:

`skill_preprocess_qc_mask -> segmentation_core -> 59`

Input contract:

- `input_slide`

Expected output contract:

- `mask_tif`
- optional `region_json`
- optional overlay

Current readiness:

- `partial`

Why:

- the mask-producing segmentation branch is real and `1-foreground-segmentation`
  is locally verified.
- overlay handoff is still broken because `59` returns `completed_no_output`
  even when preflight is ready.

Known breakpoints:

- zero-output overlay tail

Auto-scheduling policy:

- allowed only when downstream consumers are mask-native
- overlay should be marked optional until `59` is fixed

## Skill 4: Multi-Resolution Tissue Prior

Skill ID: `skill_multires_tissue_prior`

Purpose:

- generate stronger tissue priors when a single-scale support mask is likely
  too weak.

PathoFlow blocks:

- `40-GrandQC`
- `57-estimate-image-spacing`
- `64-TUZI`
- `59-generate-overlays`

Recommended sequence:

`40-GrandQC? -> 57-estimate-image-spacing? -> 64-TUZI -> 59?`

Input contract:

- `input_slide`

Expected output contract:

- `mask_tif`
- optional `region_json`
- optional overlay

Current readiness:

- `declared_only`

Why:

- `64-TUZI` is clearly registered as the multi-resolution branch.
- there is no local execution proof in this pass.

Known breakpoints:

- no local manifest evidence
- overlay tail still inherits the `59` gap if included

Auto-scheduling policy:

- only expose after a deterministic task asks for tissue-prior or multiscale
  segmentation behavior

## Skill 5: Nucleus Pathomics

Skill ID: `skill_nucleus_pathomics`

Purpose:

- generate nucleus instances,
- pass those artifacts into nucleus-aware pathomics feature extraction,
- prepare graph or survival downstream analysis.

PathoFlow blocks:

- optional preprocess:
  `1-foreground-segmentation`
- preferred reviewed nucleus tools:
  `50-hovernet-pannuke-mp`
  `53-hover-next-mp`
- local legacy execution proof:
  `4-nucleus-segmentation-hovernet-pannuke`
- pathomics composite:
  `77-Pathomics-pipeline-from-slides-nucleus`

Recommended sequence:

`1-foreground-segmentation? -> 50|53 -> 77`

Input contract:

- `input_slide`

Expected output contract:

- nucleus mask
- nucleus feature table or PKL

Current readiness:

- `declared_only`

Why:

- registry evidence is strong for the reviewed chain `50|53 -> 77`
- local execution proof in this pass exists only for legacy `4`, not for
  reviewed `50` or `53`, and not for `77`

Known breakpoints:

- execution gap between reviewed preferred nucleus tools and locally verified
  legacy nucleus tool
- no local manifest proof yet for the pathomics extraction stage

Auto-scheduling policy:

- prefer deterministic selection between `50` and `53`
- never route this as a generic “classification” answer
- mark downstream graph and survival analysis as separate review layers

## Skill 6: IHC Quantification

Skill ID: `skill_ihc_quantification`

Purpose:

- detect and quantify positive/negative IHC cells.

PathoFlow blocks:

- `40-GrandQC`
- `41-DeepLIIF`

Recommended sequence:

`40-GrandQC? -> 41-DeepLIIF`

Input contract:

- `input_slide`

Expected output contract:

- `cell_mask`
- optional `cell_count_csv`
- optional overlay

Current readiness:

- `declared_only`

Why:

- the registry description is strong and task-specific.
- there is no local execution trace in this pass.

Known breakpoints:

- planner currently drifts away from IHC tasks entirely

Auto-scheduling policy:

- expose only when the task explicitly mentions IHC, positive/negative cells,
  or cell quantification

## Skill 7: Prompt Segmentation

Skill ID: `skill_prompt_segmentation`

Purpose:

- use a prompt-driven segmentation route when the user wants concept-based
  segmentation rather than a disease-specific reviewed model.

PathoFlow blocks:

- `25-BiomedParse`
- optional `59-generate-overlays`

Recommended sequence:

`25-BiomedParse -> 59?`

Input contract:

- `input_slide`
- prompt-like target concept

Expected output contract:

- `mask_tif`
- optional overlay

Current readiness:

- `declared_only`

Why:

- the registry explicitly records this as prompt-based segmentation.
- there is no local execution proof in this pass.

Known breakpoints:

- if the overlay tail is requested, it inherits the `59` zero-output problem

Auto-scheduling policy:

- do not prefer this over a disease-specific reviewed segmentation tool unless
  the user intent is clearly prompt-driven

## Skill 8: Virtual Modality

Skill ID: `skill_virtual_modality`

Purpose:

- generate virtual modality outputs rather than masks or classifications.

PathoFlow blocks:

- `39-HE-transfer-to-SHG`
- `67-GigaTIME`

Recommended sequence:

- `39-HE-transfer-to-SHG`
  or
- `67-GigaTIME`

Input contract:

- `input_slide`

Expected output contract:

- generated image
- generated multichannel directory

Current readiness:

- `declared_only`

Why:

- both tools are clearly represented in reviewed registry flows.
- neither was locally executed in this pass.

Known breakpoints:

- no local manifest evidence
- outputs are generated imagery, so they are not standard mask-chain inputs

Auto-scheduling policy:

- treat as standalone skill family
- do not attach standard mask overlay assumptions

## Skill 9: Specialized TLS

Skill ID: `skill_specialized_tls`

Purpose:

- segment tertiary lymphoid structures and related germinal-center patterns.

PathoFlow blocks:

- `40-GrandQC`
- `61-hooknet-tls`
- optional review/export layer

Recommended sequence:

`40-GrandQC? -> 61-hooknet-tls -> review/export`

Input contract:

- `input_slide`

Expected output contract:

- `mask_tif`
- optional overlay
- optional structured result

Current readiness:

- `declared_only`

Why:

- the reviewed registry chain is explicit.
- local execution proof is absent in this pass.

Known breakpoints:

- no local manifest proof
- if overlay is requested, the same visualization fragility applies

Auto-scheduling policy:

- only expose for TLS or lymphoid-structure-specific requests

## Skill 10: Normalization Bridge

Skill ID: `skill_normalization_bridge`

Purpose:

- normalize stain appearance before a downstream model that is sensitive to
  staining differences.

PathoFlow blocks:

- `52-Global-Macenko`

Recommended sequence:

`52-Global-Macenko -> downstream_model`

Input contract:

- `input_slide`

Expected output contract:

- normalized slide artifact

Current readiness:

- `blocked`

Why:

- the local demo execution returns `success=true` but no output files

Known breakpoints:

- empty upstream output blocks the downstream chain immediately

Auto-scheduling policy:

- do not auto-insert until normalization actually emits artifacts

## Skill 11: Overlay Review

Skill ID: `skill_overlay_review`

Purpose:

- generate a readable overlay from an existing slide and existing TIF/TIFF
  mask.

PathoFlow blocks:

- `59-generate-overlays`

Recommended sequence:

`input_slide + input_mask -> 59-generate-overlays`

Input contract:

- `input_slide`
- `input_mask` with `.tif` or `.tiff`

Expected output contract:

- `overlay_png`

Current readiness:

- `blocked`

Why:

- local preflight can succeed,
- but execution returns `completed_no_output`

Known breakpoints:

- zero-file result manifest
- upstream detection masks may also violate the required file extension

Auto-scheduling policy:

- never mark this as a “safe final presentation step” until artifacts are real

## Recommended Deterministic Skill Tiers

### Tier A: Usable Core

- `skill_preprocess_qc_mask`
  Use with caution: only the foreground stage is locally proven.
- `skill_classification_screening`
  Use without overlay tail.

### Tier B: Structurally Good But Not Closed Loop

- `skill_region_segmentation`
- `skill_nucleus_pathomics`
- `skill_ihc_quantification`
- `skill_prompt_segmentation`
- `skill_specialized_tls`

### Tier C: Registry Present But Needs Execution Proof

- `skill_multires_tissue_prior`
- `skill_virtual_modality`

### Tier D: Explicitly Broken Helper Skills

- `skill_normalization_bridge`
- `skill_overlay_review`

## Scheduling Policy Recommendation

If PathoFlow is forced to work without trusting the current planner, the safer
policy is:

1. determine task family with deterministic rules first,
2. bind to one of the skills above,
3. resolve tool sequence inside the skill,
4. reject any chain that depends on `skill_overlay_review` or
   `skill_normalization_bridge` as mandatory final steps,
5. treat registry-only skills as review-mode suggestions until manifest proof is
   added.

## Bottom Line

PathoFlow already has enough structure to be described as a skill system, but
not yet enough execution closure to act like a stable one.

The most reliable current skill is still slide screening with locally verified
classification outputs. The biggest missing pieces for a real skill runtime are
planner discipline, overlay closure, normalization closure, and reviewed
execution proof for nucleus/pathomics and IHC branches.
