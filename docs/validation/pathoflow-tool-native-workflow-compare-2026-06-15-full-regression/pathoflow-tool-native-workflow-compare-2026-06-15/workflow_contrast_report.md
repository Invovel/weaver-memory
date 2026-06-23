# PathoFlow Workflow Contrast Report

This report contrasts the theoretical workflow recovered from the offline
PathoFlow replay package with the currently executable no-LLM workflow
evidence from the tool-native package.

## Theoretical Workflow

Theoretical workflow is derived from the offline baseline's dominant exact
`expected_toolchain` patterns.

```mermaid
flowchart LR
  T1["获取切片信息<br/>29-Summarize-slide-info"]
  T2["全景病理切片质量控制(GrandQC)<br/>40-GrandQC"]
  T1 -->|1850| T2
  T3["H&E前景分割<br/>1-foreground-segmentation"]
  T2 -->|742| T3
  T4["HoverNeXt细胞核分割<br/>53-hover-next-mp"]
  T3 -->|740| T4
  T5["从细胞核掩膜抽取病理组学特征<br/>77-Pathomics-pipeline-from-slides-nucleus"]
  T4 -->|1052| T5
  T6["H&E与IHC前景分割<br/>48-foreground-segmentation-beta"]
  T2 -->|260| T6
  T7["免疫组化阳性、阴性细胞检测分割(DeepLIIF)<br/>41-Deepliif"]
  T6 -->|260| T7
  T8["多类组织语义分割(私有)<br/>3-tissue-segmentation"]
  T2 -->|130| T8
  T8 -->|110| T4
  T9["三级淋巴结构与生发中心分割<br/>61-hooknet-tls"]
  T2 -->|76| T9
  T10["使用病理基础模型对全切片进行嵌入编码<br/>49-slide-embedding-all-methods"]
  T2 -->|40| T10
  T11["应用多示例学习模型至切片(使用原始切片)<br/>73-Infer-MIL-pipeline-for-slides"]
  T10 -->|20| T11
```

- 700: 29-Summarize-slide-info -> 40-GrandQC -> 1-foreground-segmentation -> 53-hover-next-mp -> 77-Pathomics-pipeline-from-slides-nucleus
- 260: 29-Summarize-slide-info -> 40-GrandQC -> 48-foreground-segmentation-beta -> 41-Deepliif
- 230: 29-Summarize-slide-info -> 40-GrandQC
- 200: 29-Summarize-slide-info -> 40-GrandQC -> 53-hover-next-mp -> 77-Pathomics-pipeline-from-slides-nucleus
- 110: 29-Summarize-slide-info -> 40-GrandQC -> 3-tissue-segmentation -> 53-hover-next-mp -> 77-Pathomics-pipeline-from-slides-nucleus

## Actually Executable Workflow

Executable workflow is limited to no-LLM demo / cpu_pseudo tools that
currently return real manifests and files.

```mermaid
flowchart LR
  A["H&E前景分割\n1-foreground-segmentation\nstatus: ok"]
  B["细胞核分割\n4-nucleus-segmentation-hovernet-pannuke\nstatus: ok"]
  C["CPU伪检测\n5/6 detection\nstatus: ok"]
  D["混叠预览\n59-generate-overlays\nstatus: ok"]
  E["染色归一化\n52-Global-Macenko\nstatus: ok"]
  A -->|foreground_mask| D
  B -->|nucleus_mask| D
  C -->|tumor_mask + report| D
  E -->|normalized_slide| C
```

- H&E前景分割: status=ok, outputs=foreground_mask
- 细胞核分割: status=ok, outputs=nucleus_mask
- CPU伪检测: status=ok, outputs=detection_result, tumor_mask, report_json
- 混叠预览: status=ok, outputs=overlay_png
- 染色归一化: status=ok, outputs=normalized_slide

## Main Gaps

- Previous offline replay runtime any-hit rate: 0.372
- Previous offline replay canonical any-hit rate: 0.5755
- Planner primary drift counts: {'wish_40_grandqc': 1, 'workflow_foreground_nucleus_pathomics_survival': 1, 'wish_41_deepliif': 1}
- Executed zero-output cases: []

## Breakpoint Summary

- sequential_chain_failure: 2

## Interpretation

- Theoretical PathoFlow workflow is much richer than the currently executable workflow.
- The biggest practical breakpoints are planner drift, downstream overlay empty outputs, empty normalization outputs, and format-contract mismatch between upstream and downstream tools.
- The repository can execute some real no-LLM tool fragments, but it cannot yet turn the recovered theoretical workflow into a stable multi-step closed loop.
