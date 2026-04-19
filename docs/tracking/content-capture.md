# Content Capture

Capture prompt and response text so the evaluator can judge your runs.
Disabled by default — you opt in with a sampling rate.

## Why capture content?

The botanu evaluator (LLM-as-judge, retrieval-quality checks, policy checks)
can only score what it can see. Without captured input/output text, the
evaluator falls back to a workflow-name placeholder and every verdict ends up
scoring the same empty string. Capture is the on-ramp to real eval verdicts
and, via the verdict rollup, to accurate event-level outcome determination.

## The knob

One config field turns the whole thing on:

```python
from botanu import enable
from botanu.sdk.config import BotanuConfig

enable(config=BotanuConfig(content_capture_rate=0.10))
```

Or via environment:

```bash
export BOTANU_CONTENT_CAPTURE_RATE=0.10
```

Recommended settings:

| Environment | Rate | Why |
| --- | --- | --- |
| Production | `0.10`–`0.20` | Enough samples for statistical eval without flooding storage |
| Staging / shadow | `1.0` | Capture everything while iterating on prompts |
| Sandbox / local | `1.0` | Capture everything |
| Unknown | `0.0` (default) | Capture nothing — privacy-safe default |

The gate is a `random.random() < rate` check per call. It is independent for
each capture point — the SDK does not coordinate across processes.

## Three capture points

### 1. Workflow-level (automatic, once per run)

`@botanu_workflow` will capture the decorated function's bound arguments as
input and its return value as output, **once per run**, when
`content_capture_rate` fires.

```python
from botanu import botanu_workflow

@botanu_workflow(
    "summarize",
    event_id=lambda req: req.id,
    customer_id=lambda req: req.tenant,
)
def summarize(req):
    return llm.summarize(req.text)
```

When the rate gate passes:

- The arguments are bound against the signature (`inspect.signature(func).bind_partial`)
  and written as `botanu.eval.input_content` on the root `botanu.run` span.
- The return value is written as `botanu.eval.output_content`.

Both fields are JSON-serialized (with a `repr` fallback) and truncated to
4096 characters. The decision is made once per call so you never land a
half-captured pair.

### 2. LLM-span-level (explicit, per model call)

[`LLMTracker`](llm-tracking.md#set_input_content-set_output_content) exposes
`set_input_content()` and `set_output_content()` for per-call capture. Use
these when you want the *actual* prompt / response text on a specific LLM
span rather than the bound workflow arguments.

```python
from botanu.tracking.llm import track_llm_call

with track_llm_call(provider="openai", model="gpt-4") as tracker:
    tracker.set_input_content(prompt)
    response = openai.chat.completions.create(model="gpt-4", messages=[...])
    tracker.set_output_content(response.choices[0].message.content)
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
```

These calls no-op when `content_capture_rate` is 0.0. Each call evaluates
the rate independently.

### 3. Data/tool-span-level

`track_tool_call()` and the data-tracking helpers follow the same pattern —
expose optional content setters that respect the same rate. See
[Data Tracking](data-tracking.md) for the specific signatures.

## What gets written

| Attribute | Written by | Source |
| --- | --- | --- |
| `botanu.eval.input_content` | `@botanu_workflow` | Bound function arguments (JSON) |
| `botanu.eval.output_content` | `@botanu_workflow` | Return value (JSON) |
| `botanu.eval.input_content` | `LLMTracker.set_input_content()` | Explicit prompt text |
| `botanu.eval.output_content` | `LLMTracker.set_output_content()` | Explicit response text |

All values are truncated to 4096 characters before being stamped.

## PII handling

The SDK **does not scrub PII**. Scrubbing happens downstream:

1. **Collector** — runs a regex redaction pass on `botanu.eval.*` attributes
   (credit-card, email, phone, API-key patterns) before forwarding.
2. **Evaluator** — runs a Microsoft Presidio NER pass before storing captured
   text against the eval record.

If you have strict PII requirements, keep `content_capture_rate=0.0` and
drive eval off explicit tool/score annotations instead. The capture pipeline
is opt-in precisely so you can stay private by default.

## Verifying capture is on

After setting a non-zero rate, run a workflow and check the span attributes
with your normal OTel tooling. A captured span will carry
`botanu.eval.input_content` and `botanu.eval.output_content` as string
attributes. If they are absent, check in order:

1. `BotanuConfig.content_capture_rate` is actually > 0.0 in the running
   process (`BotanuConfig.from_yaml(...)` and env precedence can surprise
   you — print `get_config().content_capture_rate` to be sure).
2. You are inside a span (`@botanu_workflow` or `track_llm_call` scope).
3. The random gate didn't miss — at `rate=0.1`, ~90% of calls will look
   empty. Set the rate to `1.0` temporarily to confirm plumbing.

## See also

- [LLM Tracking → set_input_content / set_output_content](llm-tracking.md#set_input_content-set_output_content)
- [Configuration → content_capture_rate](../getting-started/configuration.md)
- `src/botanu/sampling/content_sampler.py` — the rate gate
- `src/botanu/sdk/decorators.py` — workflow-level auto-capture
- `src/botanu/tracking/llm.py` — LLM-span capture
