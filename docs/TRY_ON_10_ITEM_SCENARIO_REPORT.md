# Try-On Canonical Proxy and 10-Item StylingSession Scenario Report

**Execution mode:** isolated FastAPI `TestClient` with in-memory SQLite and a signed test JWT.  
**Purpose:** validate the real HTTP workflow without touching a user database, broker, storage provider, or GPU worker.

## 1. Canonical proxy Try-On flow

The server resolves an outfit only from the immutable session wardrobe snapshot. The lifecycle tested is:

```text
StylingSession inputs_resolved
  → OutfitDecisionRun ready
  → TryOn preview (preview_outfit_id)
  → user_reviewing; selected_outfit_id remains null
  → explicit SelectOutfitCandidate
  → outfit_selected
  → final TryOn
```

Preview and final selection are separate commands. Preview creates a durable `TryOnRun` and audit evidence but cannot set `StylingSession.selected_outfit_id`; the separate selection endpoint is required for final choice.

| Case | Requested mode | Actual mode/status | Binding behavior | Expected user-facing interpretation |
|---|---|---|---|---|
| Explicit proxy | `canonical_proxy` | `canonical_proxy` / `proxy` | Category proxy binding has no mesh URI. | A simple avatar-attached category preview. |
| Candidate missing from snapshot | Any | `canonical_proxy` / `unavailable` | No bindings are returned. | The decision references no current immutable wardrobe asset; do not invent geometry. |
| Mixed quality rigged candidate | `rigged_template` | `canonical_proxy` / `pending_review` | Every item is proxied when any selected item lacks a full approved gate. | The combination must not show a partly approved rigged look as if it were coherent fitting. |
| Fully approved mesh evidence | `rigged_template` | `rigged_template` / `approved` | Approved mesh URI and anchors are returned. | Visual mesh binding only; still no guarantee of physical fit. |

The edge-case suite contains four resolver cases and one HTTP flow. Its latest run passed **5/5**. The artifacts are `backend/tests/test_try_on_proxy_edge_cases.py`, `backend/tests/test_p1_p2_api_contract.py`, and `backend/reports/try_on_proxy_edge_cases.txt`.

> `canonical_proxy` follows avatar transforms by category/anchor. It does **not** establish garment reconstruction, texture transfer, collision handling, cloth dynamics, size accuracy, or physical try-on.

## 2. 10-item owned-only wardrobe scenario

The scenario uses exactly ten active, approved canonical wardrobe assets and `availability_policy=owned_only`.

| Slot | Item |
|---|---|
| Top | White structured shirt; beige knit polo; fluid bohemian blouse |
| Bottom | Black high-waist trouser; cream pleated midi skirt; technical black jogger |
| Outerwear | Navy blazer; camel trench coat |
| Footwear | Black loafer; white minimal sneaker |

The use case was `meeting`, with style preferences `quiet_luxury`, `preppy`, and `business`; functional intents `professional_presence`, `confidence`, and `weather_protection`; business formality; subtle intensity; optional outerwear and footwear. The scenario creates a confirmed body profile, creates and activates all ten assets, creates the immutable session, runs a three-candidate decision, previews the highest candidate in requested `rigged_template` mode, selects it, and performs final proxy try-on.

| Result | Observed value |
|---|---|
| Candidate count | 3 |
| Highest candidate | Beige knit polo + cream pleated midi skirt + camel trench coat + black loafer |
| Highest score / confidence | 326.0 / 0.95 |
| Highest archetypes | `quiet_luxury`, `preppy`, `business` |
| Preview requested / actual | `rigged_template` → `canonical_proxy` |
| Preview quality | `pending_review` with 4 bindings |
| Selection before explicit action | `null` |
| Selection after explicit action | Highest candidate ID; session `outfit_selected` |
| Final requested / actual | `canonical_proxy` → `canonical_proxy` |
| Final quality | `proxy` with 4 bindings |

The ranking remained inside the ten-item snapshot. Its trade-offs correctly surfaced incomplete weather metadata and footwear/formality mismatches rather than hiding them. The full JSON evidence is `backend/reports/style_session_10_item_scenario.json`, produced by `backend/scripts/run_style_session_10_item_scenario.py`.

## 3. Style knowledge specification review

`STYLE_KNOWLEDGE_AND_3D_VIEWER_SPEC.md` defines the current deterministic policy boundary. The archetype taxonomy is metadata used in scoring and explanation; it is not a personality label or an assertion that a garment is universally appropriate.

| Rule | Implemented evidence |
|---|---|
| Occasion and formality | `occasion_match` and `formality_match` score evidence or explicit trade-offs. |
| Personal style direction | `style_match`, weighted main-layer archetype inference, and candidate diversity filtering. |
| Functional needs | `functional_intent_support`, outfit-level intent coverage, mobility, weather, modesty, and care rules. |
| Availability | `owned_only` preserves snapshot restriction; discovery policies visibly request confirmation for non-owned garments. |
| Explainability | Candidate includes score, evidence, trade-offs, `style_story`, `style_archetypes`, and `functional_highlights`. |
| 3D integrity | Preview does not select. Requested rigged modes fall back whenever quality evidence is incomplete. |

## 4. Current limitations and next engineering gates

The proxy geometry is a user-flow visualization layer. It cannot determine drape, hidden garment panels, fabric thickness, sizing ease, collision, or real body fit. A true garment mesh must pass stored GLB, skeleton, anchor, skin-weight, scale, bounds, intersection, and human-review gates before the resolver returns an approved mesh binding.

The 10-item test validates deterministic decision mechanics and workflow state. It does not validate fashion quality across cultures, seasons, brands, personal comfort, accessibility, or real wardrobe photographs. Those need a reviewed evaluation corpus and human feedback loop before any model is treated as an expert.
