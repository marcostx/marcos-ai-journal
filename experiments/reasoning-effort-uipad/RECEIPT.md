# UiPad Cursor receipt

Paste this file into a **new Cursor chat**. Select the model and reasoning effort in the Cursor UI **before** you send the message. One chat = one model + one effort.

Do not use API keys. You are the model under test.

## What you are

Copy these labels from the Cursor UI. Do not substitute a different model.

- `model`: one of `GPT-5.6 Sol`, `Claude Opus 5`, `Cursor Grok 4.6`
- `reasoning_effort`: one of `none`, `low`, `medium`, `high`, `xhigh`, `max`

If this effort is not offered for the selected model, stop and write `unsupported` into `runs/unsupported.md`. Do not pretend to run a different effort.

## Conditions still required

| Model | Efforts |
|---|---|
| GPT-5.6 Sol | none, low, medium, high, xhigh, max |
| Claude Opus 5 | low, medium, high, xhigh, max |
| Cursor Grok 4.6 | low, medium, high, xhigh |

A condition is done when `results/uipad_results.jsonl` has all 32 `row_id`s for that pair.

## Files

Work in `experiments/reasoning-effort-uipad/`.

| File | When to open |
|---|---|
| `eval_set.json` | Now. Questions and screenshot paths. |
| `eval_images/*.png` | Now. Visual input only. |
| `eval_gold.json` | **Never until raw answers are written.** Scoring script reads it. |
| `results/uipad_results.jsonl` | After answering, to skip duplicates. |
| `runs/<model>__<effort>.jsonl` | You write this. |

## Steps

1. Read `eval_set.json`. If `eval_images/` is missing files, run `python3 fetch_eval_images.py`.
2. Read `results/uipad_results.jsonl` if it exists. Skip any `row_id` already stored for this `model` + `reasoning_effort`.
3. For each remaining item, in order:
   - Open the PNG in `image`.
   - Do not open accessibility trees, gold answers, or other questions' discussions.
   - Answer using only that screenshot and this prompt:

```text
Answer the question using only the attached screenshot.

Question: {question}

Return only the final answer:
- number: a numeric value
- yes/no: Yes or No
- string: the shortest exact answer visible or inferable from the screen
- coordinates: [[x1, y1], [x2, y2]], representing the target bounding box
```

4. After **all** remaining items have raw answers, write `runs/<slug>.jsonl` with one JSON object per line. `<slug>` is the model and effort in lowercase with spaces as `-`, for example `claude-opus-5__low.jsonl`.

```json
{"row_id":"q00","screen_id":1707127615,"question":"...","model":"Claude Opus 5","reasoning_effort":"low","raw_response":"...","input_tokens":null,"reasoning_tokens":null,"output_tokens":null,"latency_ms":null}
```

`raw_response` is your answer. Leave token fields `null` if Cursor does not show them.

5. Then run:

```bash
python3 score_and_plot.py --run runs/claude-opus-5__low.jsonl
```

Use the file you just wrote. This appends scored rows to `results/uipad_results.jsonl` and rebuilds `charts/` from **every** completed condition.

6. Reply with:
   - model and effort
   - this condition's pass@1
   - the cumulative table printed by the script
   - which conditions are still missing

If the context window fills, stop after a complete subset of `row_id`s, write the JSONL for those rows, run the scorer, and say which IDs remain. The next chat with the same model and effort continues from the gaps.

## Rules

- One attempt per question. No retries after seeing the score.
- Do not look at `eval_gold.json` before the scorer runs.
- Do not copy answers from a previous model's run.
- Start a new chat when you change model or effort.
