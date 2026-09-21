# Does reasoning effort improve UiPad accuracy?

**Short answer:** extra reasoning helped only where the task was spatial. Cursor Grok 4.6 jumped from 0.719 at `low` to 1.000 at `medium` and stayed there. Claude Opus 5 was already strong at `low` (0.906) and reached a perfect 1.000 only at `xhigh`. GPT-5.6 Sol never scored a coordinate box (`IoU = 0` at every effort) and finished no higher at `max` than at `none`.

Yes/no questions were already solved at the lowest available effort. Number and string questions were near ceiling. Token counts and latency were not recorded in Cursor, so this report cannot say whether any accuracy gain paid for its cost.

## Research question

The design in [experiments/reasoning-effort-uipad/README.md](../experiments/reasoning-effort-uipad/README.md) asks whether additional reasoning improves macOS UI understanding on [UiPad](https://huggingface.co/datasets/macpaw-research/UiPad), or whether it only adds latency and tokens.

The pre-registered hypothesis was that higher effort would help **counting** and **spatial** questions, and would add little for **text recognition** and **yes/no**.

## Design

Three Cursor models were run at every effort that model exposes:

| Model | Efforts run |
|---|---|
| GPT-5.6 Sol | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| Claude Opus 5 | `low`, `medium`, `high`, `xhigh`, `max` |
| Cursor Grok 4.6 | `low`, `medium`, `high`, `xhigh` |

Claude has no `none`. Grok has no `none` or `max`. Those gaps are product limits, not missing runs.

The sample is the frozen 32-question set in `eval_set.json` (UiPad test split, 8 questions per answer type, seed 0, 26 unique screenshots). Each condition used the same screenshots and the same prompt. Model and effort were selected in the Cursor UI; a new chat was opened for every pair. Gold labels were not opened until after raw answers were written. There was one attempt per question.

Scoring is deterministic (`score_and_plot.py`):

- **Number:** parsed float within 1% or 0.01 of gold
- **Yes/no:** case-insensitive match after normalization
- **String:** case-insensitive match after trimming whitespace and punctuation
- **Coordinates:** `IoU >= 0.5` against the gold box

The primary metric is pass@1. Every condition has all 32 `row_id`s (480 scored rows, 0 parse failures, 0 run errors).

Usage fields (`input_tokens`, `reasoning_tokens`, `output_tokens`, `latency_ms`) are `null` in every record. Cursor did not expose them, so token, latency, and “correct answers per 1,000 tokens” metrics are unavailable.

## Overall accuracy

![pass@1 versus reasoning effort](../experiments/reasoning-effort-uipad/charts/pass_at_1_vs_effort.svg)

| Model | Effort | n | Correct | pass@1 | 95% Wilson CI |
|---|---|---:|---:|---:|---|
| GPT-5.6 Sol | none | 32 | 24 | 0.750 | 0.58–0.87 |
| GPT-5.6 Sol | low | 32 | 22 | 0.688 | 0.51–0.82 |
| GPT-5.6 Sol | medium | 32 | 24 | 0.750 | 0.58–0.87 |
| GPT-5.6 Sol | high | 32 | 23 | 0.719 | 0.55–0.84 |
| GPT-5.6 Sol | xhigh | 32 | 23 | 0.719 | 0.55–0.84 |
| GPT-5.6 Sol | max | 32 | 23 | 0.719 | 0.55–0.84 |
| Claude Opus 5 | low | 32 | 29 | 0.906 | 0.76–0.97 |
| Claude Opus 5 | medium | 32 | 30 | 0.938 | 0.80–0.98 |
| Claude Opus 5 | high | 32 | 30 | 0.938 | 0.80–0.98 |
| Claude Opus 5 | xhigh | 32 | 32 | 1.000 | 0.89–1.00 |
| Claude Opus 5 | max | 32 | 30 | 0.938 | 0.80–0.98 |
| Cursor Grok 4.6 | low | 32 | 23 | 0.719 | 0.55–0.84 |
| Cursor Grok 4.6 | medium | 32 | 32 | 1.000 | 0.89–1.00 |
| Cursor Grok 4.6 | high | 32 | 31 | 0.969 | 0.84–0.99 |
| Cursor Grok 4.6 | xhigh | 32 | 32 | 1.000 | 0.89–1.00 |

With n = 32, intervals are wide. Adjacent GPT and Claude rows overlap almost completely. The one movement that is hard to treat as noise is Grok `low` → `medium`: 9 questions flipped from wrong to right and none flipped the other way (exact McNemar *p* = 0.0039). Claude `low` → `xhigh` is +3 / −0 (*p* = 0.25). GPT `none` → `max` is +0 / −1.

Effort labels are not comparable across families. Grok `medium` is not the same compute as Claude `medium`.

## Accuracy by answer type

The hypothesis splits cleanly once the four types are plotted separately.

### Yes/no — no headroom

![pass@1 versus effort for yes/no](../experiments/reasoning-effort-uipad/charts/pass_at_1_yes_no.svg)

Every model, at every effort, scored **8/8**. Extra reasoning cannot help a type that is already solved.

### Number — almost solved, one low-effort miss each

![pass@1 versus effort for number](../experiments/reasoning-effort-uipad/charts/pass_at_1_number.svg)

| Model | Lowest effort | Highest effort | Misses |
|---|---|---|---|
| GPT-5.6 Sol | 8/8 at `none` | 8/8 at `max` | `low` answered 2 instead of 1 on q28 (text fields on the top of a modal) |
| Claude Opus 5 | 8/8 at `low` | 8/8 at `max` | none |
| Cursor Grok 4.6 | 7/8 at `low` | 8/8 at `xhigh` | `low` counted 11 sidebar items instead of 7 on q20 |

Higher effort repaired those two counting misses and did not create new ones. That is consistent with the hypothesis, but it is two items, not a trend.

### String — one ambiguous window title

![pass@1 versus effort for string](../experiments/reasoning-effort-uipad/charts/pass_at_1_string.svg)

Seven of eight string items were solved by every condition. The remaining item is q15: *“What is the title of current window?”* Gold is **AI Characters** (the modal). Several runs answered **Typing Mind** (the app title bar behind the modal).

| Model | Efforts that answered *AI Characters* |
|---|---|
| GPT-5.6 Sol | `none`, `medium` |
| Claude Opus 5 | `xhigh` only |
| Cursor Grok 4.6 | `medium`, `high`, `xhigh` |

This is not a recognition failure. Both strings are on screen. Higher effort sometimes picked the modal, sometimes did not. GPT got worse at this item as effort increased.

### Coordinates — where effort actually matters

![pass@1 versus effort for coordinates](../experiments/reasoning-effort-uipad/charts/pass_at_1_coordinates.svg)

| Model | `none` | `low` | `medium` | `high` | `xhigh` | `max` | Mean IoU at best effort |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Sol | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 | 0.00 |
| Claude Opus 5 | — | 6/8 | 7/8 | 7/8 | **8/8** | 7/8 | 0.85 (`xhigh`) |
| Cursor Grok 4.6 | — | 1/8 | **8/8** | 7/8 | **8/8** | — | 0.95 (`xhigh`) |

GPT’s boxes parse cleanly and point at the right control, but they live in a different pixel space than the gold boxes (often ~1.3–2× smaller). Mean IoU is 0.00 at every effort. Raising reasoning effort does not fix a coordinate-convention mismatch.

Claude and Grok already use the screenshot’s native pixel space. Their remaining errors are tight boxes around the correct control that miss `IoU >= 0.5`:

- q07 (Chrome reload): Claude `low` IoU 0.03; Grok `low` IoU 0.15. Both recover from `medium` up.
- q08 (Reminders +): the recurring near-miss. Claude is 0.20–0.45 except at `xhigh` (0.88). Grok `high` is 0.42; `medium` and `xhigh` pass.
- Grok `low` misses 7 of 8 coordinate items (mean IoU 0.25) and then jumps to mean IoU 0.88 at `medium`.

## What changes as effort increases

Paired, same-question flips from the lowest available effort to the highest:

| Model | Lowest → highest | Improved | Degraded | Unchanged | Share of items that ever flip |
|---|---|---:|---:|---:|---:|
| GPT-5.6 Sol | `none` → `max` | 0 | 1 | 31 | 2 / 32 (6%) |
| Claude Opus 5 | `low` → `max` | 1 | 0 | 31 | 3 / 32 (9%) |
| Cursor Grok 4.6 | `low` → `xhigh` | 9 | 0 | 23 | 9 / 32 (28%) |

Items that move:

- **GPT:** q15 (string) and q28 (number). Both are correct at `none` and one or both fail at higher effort. Coordinates never move.
- **Claude:** q07 becomes correct from `medium` onward; q08 and q15 become correct only at `xhigh` and regress at `max`.
- **Grok:** seven coordinate items, plus q15 and q20, become correct at `medium` and stay correct except q08 at `high`.

`max` is not strictly better than `xhigh`. Claude drops two items when going from `xhigh` to `max` (q08 IoU 0.88 → 0.45; q15 back to *Typing Mind*). Grok `high` drops q08 relative to `medium`.

## Lowest-effort point on the accuracy frontier

Cost is unmeasured, so “efficient” here means **lowest offered effort that reaches that model’s best pass@1**.

| Model | Best pass@1 | Lowest effort that hits it | Gain vs that model’s lowest effort |
|---|---:|---|---|
| GPT-5.6 Sol | 0.750 | **`none`** (tied with `medium`) | 0.000 (`none` → `max`: −0.031) |
| Claude Opus 5 | 1.000 | **`xhigh`** | +0.094 (`low` → `xhigh`) |
| Cursor Grok 4.6 | 1.000 | **`medium`** | +0.281 (`low` → `medium`) |

If the goal is “good enough UI reading” rather than a perfect click box, Claude `low` (0.906) and GPT `none` (0.750, limited entirely by coordinates) already capture every yes/no, number, and almost every string.

## Validity checks

- **Same items in every cell.** All 15 conditions contain q00–q31.
- **Formatting vs meaning.** Every failure parsed. GPT’s coordinate answers are well-formed boxes with `IoU = 0`. Claude/Grok misses are under-threshold boxes or the q15 title choice.
- **Screenshot resolution.** Local PNGs are the original UiPad files (for example Chrome q07 is 2400×1632; Reminders q08 is 1536×1472). Gold boxes sit on that pixel grid. Claude and Grok match it; GPT does not.
- **Coordinate convention.** The prompt asks for `[[x1, y1], [x2, y2]]` and does not say “original image pixels.” GPT consistently answers in another space. That is a prompt/protocol gap as much as a model gap.
- **Small-n caution.** A 3-point Claude move is inside the Wilson interval. Only Grok’s `low` → `medium` jump is a clear paired difference.
- **Dataset pin.** Images were fetched from Hugging Face `main` (`fetch_eval_images.py`). `eval_set.json` does not store a commit hash. The 32-item sample itself is frozen in-repo.
- **q15 wording.** “Current window” is underspecified when a modal sits on an app window. That item should not be read as a pure OCR test.

## Did added reasoning help?

| Question from the design | Result |
|---|---|
| Does higher effort raise pass@1? | **Yes for Grok** (`low` → `medium`). **Weakly for Claude** (perfect only at `xhigh`, then a regression at `max`). **No for GPT** (best at `none` / `medium`). |
| Where does it help? | **Coordinates**, and two counting/title items at low effort. Not yes/no. |
| Does it justify the cost? | **Unknown.** Tokens and latency were not captured. Qualitatively, Grok’s whole gain arrives at `medium`; Claude’s last two points arrive only at `xhigh` and disappear at `max`. |
| Most efficient effort | GPT **`none`**; Claude **`xhigh`** if a perfect score is required, else **`low`**; Grok **`medium`**. |

The useful negative result the protocol asked for is real for GPT-5.6 Sol: more reasoning did not produce a measurable pass@1 gain on this sample, and it did not repair the coordinate-space failure that caps the model at 0.75. The useful positive result is also real for Cursor Grok 4.6: moving off `low` is the entire experiment for that model.
