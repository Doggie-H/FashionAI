# Style Knowledge, Wardrobe-Aware Ranking, and 3D Viewer Specification

## Objective

The styling engine must propose several **meaningfully different** outfits from the user’s active wardrobe snapshot, conditioned on a selected use case and style intent. It must explain why an outfit was selected, identify compromises and abstain when the wardrobe cannot satisfy required slots. It must not turn a category proxy or an unapproved mesh into a claim of real garment fit.

## Style taxonomy

The V1 taxonomy expands existing tags with `quiet_luxury`, `preppy`, `edgy`, `bohemian`, `athleisure`, `utility`, `modest`, `resort`, `creative`, and `vintage`. These tags are metadata, not social judgments. A garment may have several tags but a candidate must receive a coherent style-archetype summary rather than an unbounded list of labels.

The use-case taxonomy adds `interview`, `meeting`, `presentation`, `celebration`, `weekend`, `gym`, `outdoor`, `home`, `cocktail`, and `wedding_guest`. It is additive to existing daily/work/date/event/travel/formal use cases, so historic session snapshots remain valid.

| Context signal | Purpose in ranking | Typical result |
|---|---|---|
| `occasion` | Hardest relevance signal. | Candidate is rewarded or penalized based on garment occasion metadata. |
| `preferred_styles` | Personal visual direction. | Rewards style overlap and creates style archetype labels. |
| `intent_tags` | Functional/emotional need, such as comfort, photo readiness or weather protection. | Scores mobility, modesty, weather and garment knowledge attributes. |
| `formality_target` | Desired degree of polish. | Rewards garments with compatible formality metadata. |
| `style_intensity` | Subtle, balanced or statement expression. | Avoids overselling a statement garment when a subtle look is requested. |
| `optional_slots` | Enables outerwear, belt, footwear or accessory variations. | Produces outfits with optional layers only where compatible. |
| active wardrobe snapshot | Availability authority. | `owned_only` never silently substitutes catalog garments. |

## Catalog knowledge additions

Each canonical garment adds `formality_level`, `statement_level`, `care_level`, `coverage_level`, `occasion_notes`, `style_notes`, `color_role`, `pairing_hints`, `avoid_pairing_with`, and typed intent support. These fields provide explainable policy inputs; they are not a claim that any garment is universally appropriate.

## Deterministic ranking

The ranking pipeline must retain its deterministic behavior. It applies body-fit and layer compatibility filters first, then scores garment and outfit combinations. New score rules are:

1. **Use-case match:** primary occasion and formality target.
2. **Style coherence:** preferred-style overlap, shared outfit archetype, and style intensity match.
3. **Functional intent:** comfort/movement/weather/coverage/care/packability support from explicit metadata.
4. **Color harmony:** conservative compatible color family matrix, with color-goal bonus and explicit trade-offs.
5. **Wardrobe coverage:** required and optional slots are selected only from active snapshot IDs when `owned_only` is selected.
6. **Candidate diversity:** top results are greedily diversified by style archetype and garment overlap so that the user sees alternatives rather than repeated near-duplicates.

Every score adjustment becomes a `DecisionEvidenceV1`, and every unsatisfied preference becomes a trade-off or confirmation request. `top_k` remains bounded to five.

## 3D experience

The Session Workspace displays the decision’s candidates as a comparison rail. **Preview 3D** creates an auditable `TryOnRun` with `preview_outfit_id` and updates avatar bindings without changing `StylingSession.selected_outfit_id`; it moves the case to `user_reviewing`. The user must separately press the server-backed select action to persist a final choice. The viewer provides front, side, rear and free orbit controls; camera controls modify only local scene view.

> `canonical_proxy` means category geometry following the avatar transform. `rigged_template` or `approved_reconstructed_asset` is rendered only when the API provides an approved binding. None of these modes proves cloth simulation or physical fit.
