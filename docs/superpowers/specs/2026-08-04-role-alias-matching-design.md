# Role Alias Matching Design

## Goal

Make the local fit prefilter recognize common Chinese and English titles for the same job family, so a configured preference such as `解决方案架构师` can match an official posting titled `Solution Architect` without weakening the existing exclusion, location, keyword, or work-mode rules.

## Scope

This release adds a small, deterministic role-family alias vocabulary to the local fit module. It does not call a remote model, change the user's saved profile, infer seniority, or treat a broad keyword such as `AI` as a role alias. The match remains a prefilter and never becomes an automatic review or application decision.

The initial families are:

- solutions architecture: `解决方案架构师`, `solution architect`, `solutions architect`, `cloud solution architect`, `ai solution architect`;
- solutions consulting: `解决方案顾问`, `solutions consultant`, `solution consultant`;
- presales: `售前`, `presales`, `pre-sales`, `sales engineer`, `technical sales`;
- customer success: `客户成功`, `customer success`, `customer success manager`;
- commercial product: `产品商业化`, `product commercialization`, `commercial product`;
- forward deployed engineering: `FDE`, `forward deployed engineer`, `forward-deployed engineer`.

Aliases are compared case-insensitively after whitespace normalization. Existing literal matching remains the first path, so user-defined custom role text still works exactly as before. A role match is true when the configured target and the job title share a known family; unrelated families do not match merely because both contain the word `AI` or `solution`.

## Explainability

The fit assessment continues to expose `role` in `matched_dimensions`. Its strength text will state that the title matched a configured role through a known alias family, including the configured target and observed title. If no family matches, the existing gap text remains direct and does not claim semantic coverage.

## Data flow

`evaluate_fit` reads the existing `target_roles` profile field, calls a private role-match helper, and emits the same `FitAssessment` shape. No database migration, export change, credential change, or browser behavior is required. The release version is bumped to `0.1.5` so public installs receive the behavior consistently.

## Failure and safety behavior

- Empty or non-string profile values continue to be ignored by the existing `_values` helper.
- Alias matching is only a positive signal; it cannot override an excluded company or excluded keyword.
- Unknown titles and languages remain unmatched rather than being guessed.
- The AI-assisted review layer, when used later, may add richer reasoning but must not replace this auditable prefilter.

## Testing

Add focused unit tests for:

1. Chinese target to English title matching, such as `解决方案架构师` to `AI Solution Architect`;
2. English target to Chinese title matching, such as `customer success` to `客户成功经理`;
3. non-matching role families remaining unmatched;
4. the existing literal match and exclusion behavior remaining intact.

Run the full 89-test baseline suite plus the new tests, the public-release preflight, official plugin validator, release archive privacy check, and an extracted package smoke test before publishing.
