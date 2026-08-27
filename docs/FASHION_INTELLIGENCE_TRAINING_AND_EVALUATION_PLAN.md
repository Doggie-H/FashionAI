# Fashion Intelligence: Knowledge, Evaluation, and Controlled Learning Plan

**Author:** Manus AI  
**Status:** implementation roadmap; no claim that a fashion-expert model has been trained.

## Executive position

A capable AI Stylist should not be implemented as a single free-form prompt that appears knowledgeable. It needs separate perception, wardrobe normalization, retrieval, constraint reasoning, ranking, explanation, reviewer override, and feedback-learning boundaries. The current project already has an explainable deterministic ranker and a versioned wardrobe/session snapshot. The next objective is to improve the knowledge and evidence supplied to that ranker, then evaluate any model-assisted reasoning against human-reviewed cases before it can influence recommendations.

> A public image dataset can support perception research, but it cannot by itself establish a model’s competence to judge personal comfort, physical fit, culturally sensitive appropriateness, or a user’s style identity.

## 1. Target intelligence architecture

| Layer | Responsibility | Production rule |
|---|---|---|
| Canonical wardrobe knowledge | Stable garment attributes, layers, colors, occasion, care, coverage, formality, pairing and avoidance rules. | Version every catalog release and keep source/license provenance. |
| Personal wardrobe memory | Owner-scoped active garment revisions, wear history and explicit feedback. | Use only consented data; never merge identities into public training data. |
| Deterministic constraint layer | Availability, required slots, formality, weather, movement, modesty, budget and quality gates. | Hard constraints cannot be overridden by an LLM. |
| Retrieval and knowledge layer | Retrieves only licensed, reviewed style guides, brand/care references and project-approved rubrics relevant to the request. | Cite source/version in the generated reasoning record. |
| Model-assisted interpretation | Converts user language and garment-image observations into typed tags, uncertainty and candidate explanations. | Strict JSON schema, confidence, abstention, no direct database writes. |
| Decision policy | Combines verified structured facts with ranker scores and diversity logic. | Persist rule/model/prompt/catalog versions and full evidence. |
| Human review and evaluation | Samples risky/low-confidence cases, creates evaluation labels and approves policy changes. | Reviewer labels are immutable training/evaluation evidence. |

## 2. Data program before any fine-tuning

The first high-value asset is not a large generic model; it is a legally usable, structured corpus of styling cases. Create a consented `StyleCase` dataset in a separate evaluation store. Each record should preserve only the minimum data needed for the task and must be de-identifiable before it is used outside the owner’s request path.

| Field group | Minimum content | Why it matters |
|---|---|---|
| Case context | Occasion, season/weather, formality, mobility, coverage, budget, desired intensity and user language. | Separates a business-meeting choice from an event, travel, sport or daily choice. |
| Wardrobe snapshot | Canonical item IDs, approved metadata/revision, availability and optional image quality indicators. | Ensures that learning does not propose unavailable or unreviewed items. |
| Candidate set | Ranker-generated candidates, evidence, trade-offs, abstention and catalog/rule version. | Enables pairwise preference and error analysis without inventing ground truth. |
| User feedback | Like/dislike/skip, reason codes, optional structured note, confidence, consent flag. | Provides a weak signal; it must not be treated as expert truth automatically. |
| Reviewer label | Rubric decision, issue type, rationale and disagreement marker from qualified reviewers. | Creates high-quality labels for evaluation and later supervised improvement. |
| Outcome boundaries | Whether a look was merely viewed, selected, worn, or later corrected. | Prevents the system from equating a click with real-world satisfaction. |

No synthetic “expert labels” should be introduced merely to inflate evaluation numbers. A training/validation/test split must be performed by user and wardrobe, not random item row, to prevent leakage from the same garment or owner into every split.

## 3. Controlled capability milestones

| Milestone | Deliverable | Offline gate before rollout | Online guardrail |
|---|---|---|---|
| M1: Knowledge completeness | Expand canonical metadata and pairing/avoidance rules with source provenance. | Schema validation and reviewer acceptance of each catalog batch. | Feature flag by catalog version; rollback to prior version. |
| M2: Retrieval-assisted explanation | Retrieval index of licensed, reviewed fashion/care guidance tied to typed context. | Citation coverage, unsupported-claim rate and abstention tests. | Retrieved sources are attached to audit payload; no source means no factual claim. |
| M3: Visual garment intake | VLM extracts category, material cues, color, silhouette and uncertainty from a user image. | Held-out image tests for category/attribute error and robustness failures. | Image result remains `pending_review` when confidence or provenance is insufficient. |
| M4: Preference adaptation | Learns a user-specific re-ranker from explicit feedback and reviewer labels. | Per-user holdout utility, fairness slices and regressions against hard constraints. | Start with shadow scoring; never override owned-only, quality or safety constraints. |
| M5: Model-assisted recommendation | Model produces typed explanation or proposes score features from retrieved facts. | Human comparison, constraint-satisfaction rate, abstention calibration and audit completeness. | Schema gate, policy gate, human escalation and immediate rollback. |
| M6: Limited fine-tuning | Fine-tune only after a governed, licensed and reviewed corpus is sufficiently large and stable. | Frozen external test set, red-team cases, privacy review and reproducible model card. | Canary deployment with monitored error, complaint and override rates. |

## 4. Evaluation rubric and release gates

The project must score different capabilities independently. A fluent response is not proof that an outfit is appropriate or that a garment will fit.

| Metric family | Measurement | Release threshold policy |
|---|---|---|
| Constraint satisfaction | Required slots, owned-only policy, activity, weather, coverage, budget and quality gate violations. | Zero tolerance for hard-policy violation; any violation blocks rollout. |
| Fashion coherence | Independent reviewer pairwise preference and rubric compliance for top candidates. | Establish a baseline first; only promote when confidence intervals improve over current deterministic baseline. |
| Diversity | Distinct archetype and item-overlap distribution among top candidates. | No release if alternatives collapse into near duplicates without a documented reason. |
| Personal utility | Explicit feedback, later correction and selection-without-immediate-reversal. | Treat as a monitored signal, not universal fashion truth. |
| Perception quality | Category, attribute, segmentation, image-quality and uncertainty calibration on held-out data. | Low confidence must route to review rather than optimistic auto-activation. |
| Explanation integrity | Evidence traceability, claim-source coverage, contradiction and hallucination rate. | All model-assisted claims need structured evidence; unsupported claims are rejected. |
| 3D integrity | Percentage of proxy/approved mesh states accurately labeled; quality gate regressions. | A proxy cannot be rendered or described as physical fitting. |

## 5. Model-assisted workflow, not autonomous fashion authority

A cost-aware path is to use a small structured-output model for catalog/image tagging, programmatic schema/confidence validation, and a stronger model only for low-confidence or reviewer-bound cases. The live sandbox catalog currently exposes structured-output and vision-capable model families, but the application must select a model at deployment from the live catalog rather than hard-code an ID. Any API call must return a strict typed record such as `StyleInterpretationV1`, not prose that directly changes an outfit decision.

```text
User request or garment photo
  → typed parser/VLM (schema + confidence + provenance)
  → policy validation and retrieval of reviewed knowledge
  → deterministic ranker produces candidates
  → optional model explanation over persisted evidence only
  → user preview / explicit selection / feedback
  → reviewer triage for low confidence, disagreement or safety/quality flags
  → versioned evaluation corpus and offline re-ranker experiments
```

The local RTX 3050 Laptop GPU with 4 GB VRAM remains unsuitable for loading or fine-tuning a heavy vision-language model and for garment reconstruction. Heavy visual inference belongs on a separate remote GPU worker, while small metadata/ranking operations stay deterministic and local. Fine-tuning must not begin until data governance, holdout evaluation, licenses and remote compute are approved.

## 6. Initial implementation backlog

| Priority | Work item | Acceptance evidence |
|---|---|---|
| P0 | Add catalog-source provenance, canonical aliases, more weather/material/care metadata and reviewer approval workflow. | Versioned metadata import with review/audit and no schema violations. |
| P0 | Define `StyleCase`, `ReviewerRubric`, `EvaluationSlice`, consent and deletion contracts. | Alembic migration, owner isolation, reviewer tests and data-retention policy. |
| P0 | Build a reviewer workspace for pairwise candidate quality, explanation correctness and abstention correctness. | Immutable labels linked to decision/catalog/rule version. |
| P1 | Create a small, real, consented seed corpus with Vietnamese context/occasion/style language. | Human-reviewed, deduplicated cases split by owner/wardrobe; no invented labels. |
| P1 | Add offline evaluation runner with constraint, preference, diversity, calibration and error-slice reports. | Reproducible report for baseline and each candidate policy version. |
| P1 | Add retrieval corpus only from licensed/reviewed sources, with document chunks, source records and access controls. | Every explanation can display a source/version or abstains. |
| P2 | Deploy VLM extraction on remote GPU in shadow mode; compare structured outputs against reviewers. | Quality, latency, cost and uncertainty acceptance gates are met. |
| P3 | Evaluate a user-specific re-ranker and optional fine-tuning after approved dataset scale. | Frozen test results exceed baseline without hard-constraint regressions. |

## References

[1] [DeepFashion2 Dataset](https://github.com/switchablenorms/deepfashion2)  
[2] [Fashionpedia](https://fashionpedia.github.io/home/)  
[3] [DeepFashion Database, CUHK MMLab](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html)  
[4] [Computational Technologies for Fashion Recommendation](https://dl.acm.org/doi/full/10.1145/3627100)  
[5] [FashionFail: Addressing Failure Cases in Fashion Object Detection and Segmentation](https://arxiv.org/html/2404.08582v1)
