# How does reasoning effort impacts in task accuracy?

This experiment evaluates whether increasing reasoning effort improves vision question-answering performance on the [UiPad dataset](https://huggingface.co/datasets/macpaw-research/UiPad).

The models compared are:

- GPT-5.6 Sol
- Claude Opus 5
- Cursor Grok 4.6

Each model is tested at every reasoning-effort level available for that model in Cursor.

## Research question

Does additional reasoning improve a model's ability to understand macOS interfaces, or does it only increase latency and token usage?

The primary hypothesis is that higher reasoning effort will help with questions that require counting or spatial interpretation, but may provide little benefit for direct text recognition and simple yes/no questions.

## Dataset

[UiPad](https://huggingface.co/datasets/macpaw-research/UiPad) contains screenshots from macOS applications and questions that test visual interface understanding.

The evaluation covers its four answer types:

- **Number:** counting controls or reading numeric values
- **Yes/no:** identifying interface states or the presence of elements
- **String:** reading labels, names, and values
- **Coordinates:** locating the region that should be clicked

Use the official test split. Record the dataset revision or commit hash so the experiment can be reproduced.

## Experimental design

Run every selected question once for each model and reasoning-effort combination. Change the active model and effort level directly in Cursor between runs.

Keep all other conditions fixed:

- Use the same screenshot and prompt for every model.
- Start each question in a fresh conversation to avoid context leakage.
- Do not provide the accessibility tree or information from another sample.
- Do not manually correct, clarify, or retry an answer.
- Preserve the complete response and reported token usage.
- Randomize question order, or use the same fixed order for every condition.
- Record unsupported effort levels as unavailable rather than substituting another level.

For a lower-cost pilot, select a deterministic, stratified sample containing an equal number of questions from each answer type. Run the full test split only after validating the pipeline.

## Prompt

Use the following prompt with the corresponding UiPad screenshot attached:

```text
Answer the question using only the attached screenshot.

Question: {question}

Return only the final answer:
- number: a numeric value
- yes/no: Yes or No
- string: the shortest exact answer visible or inferable from the screen
- coordinates: [[x1, y1], [x2, y2]], representing the target bounding box
```

Do not reveal the expected answer or answer type beyond these formatting instructions.

## Output record

Store one record per response:

```json
{
  "screen_id": 1707228194,
  "question": "Where should I click to switch to Dock menu?",
  "answer_type": "coordinates",
  "gold_answer": "[[20, 512], [380, 572]]",
  "model": "Claude Opus 5",
  "reasoning_effort": "high",
  "raw_response": "[[20, 512], [380, 572]]",
  "parsed_answer": "[[20, 512], [380, 572]]",
  "correct": true,
  "input_tokens": null,
  "reasoning_tokens": null,
  "output_tokens": null,
  "latency_ms": null,
  "run_timestamp": "YYYY-MM-DDTHH:MM:SSZ"
}
```

Use the exact model name and effort label displayed by Cursor. Leave unavailable usage or latency fields as `null`.

## Scoring

Parse the final response into the type required by the question, then score it deterministically:

- **Number:** exact match, with a documented numeric tolerance if the dataset requires one
- **Yes/no:** case-insensitive exact match after normalization
- **String:** case-insensitive exact match after trimming whitespace and punctuation
- **Coordinates:** intersection over union (IoU) of the predicted and reference boxes, with `IoU >= 0.5` counted as correct

Parsing must only normalize the response. It must not reinterpret an incorrect answer or use another model to decide correctness.

## Metrics

### Primary metric

- **Accuracy (pass@1):** proportion of questions answered correctly for each model and effort level

### Secondary metrics

- Accuracy by answer type
- Mean input, reasoning, and output tokens
- Median response latency
- Correct answers per 1,000 total tokens
- Accuracy gain from the lowest to the highest effort level
- Percentage of questions whose result changes as effort increases

When the sample size permits, report 95% bootstrap confidence intervals. Because every condition uses the same questions, use paired comparisons when testing differences between effort levels.

## Analysis

For each model:

1. Plot overall accuracy by reasoning effort.
2. Break accuracy down by number, yes/no, string, and coordinates.
3. Compare accuracy against reasoning tokens and latency.
4. Identify the lowest-effort condition on the accuracy–cost frontier.
5. Review questions that change from incorrect to correct, or correct to incorrect, at higher effort.

Across models, compare both maximum accuracy and efficiency. Do not assume that effort labels represent equivalent compute across model families.

## Validity checks

- Confirm that screenshots render at their original resolution.
- Verify coordinate conventions before scoring the first batch.
- Inspect a sample of parsed answers for each answer type.
- Check that every model-effort condition contains the same question IDs.
- Separate invalid formatting from semantically incorrect answers.
- Avoid conclusions from small differences whose confidence intervals substantially overlap.

## Expected outputs

- Raw response records in JSONL
- Parsed and scored results
- Overall and per-answer-type summary metrics
- Accuracy-versus-effort and accuracy-versus-cost charts
- A short report describing whether added reasoning helped, where it helped, and whether the improvement justified its cost

## Success criterion

The experiment should determine, for each model, whether increasing reasoning effort produces a measurable pass@1 improvement on UiPad and identify the most efficient effort level. A useful negative result is that higher effort increases cost without a reliable accuracy gain.
