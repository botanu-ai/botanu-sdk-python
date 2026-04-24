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

One env var turns the whole thing on:

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

`botanu.event` will capture the decorated function's bound arguments as
input and its return value as output, **once per run**, when
`content_capture_rate` fires.

```python
import botanu

@botanu.event(
    workflow="summarize",
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
| `botanu.eval.input_content` | `botanu.event` | Bound function arguments (JSON) |
| `botanu.eval.output_content` | `botanu.event` | Return value (JSON) |
| `botanu.eval.input_content` | `LLMTracker.set_input_content()` | Explicit prompt text |
| `botanu.eval.output_content` | `LLMTracker.set_output_content()` | Explicit response text |

All values are truncated to 4096 characters before being stamped.

## PII handling

The SDK scrubs PII **in-process** before a span attribute is written. This is
on by default — you do not need to configure anything to get it. Downstream
collector + evaluator passes remain as belt-and-suspenders.

Pipeline for every captured string:

```text
customer text
    ↓
content_capture_rate gate           (skip capture entirely)
    ↓
regex scrub (default patterns)      # src/botanu/sdk/pii.py
    ↓
optional Presidio NER               # pip install botanu[pii-nlp]
    ↓
truncate to max_chars (4096)
    ↓
span.set_attribute("botanu.eval.*_content", ...)
```

### Built-in regex patterns

Email, phone (E.164 + US), SSN, credit card (Luhn-validated), IPv4/IPv6,
JWT, bearer tokens, and common API-key prefixes (AWS `AKIA…`, GitHub
`ghp_…`, Stripe `sk_live_…`, Slack `xoxb-…`, OpenAI `sk-…`,
Anthropic `sk-ant-…`).

Matches are replaced with `[REDACTED]` by default.

### Configuration

```yaml
eval:
  content_capture_rate: 0.2
  pii:
    enabled: true               # default — opt-out is explicit
    disable_patterns: [ipv4]    # turn off specific built-ins
    custom_patterns:
      employee_id: 'EMP-\d{6}'
    use_presidio: false         # set true to add NER on top
    replacement: "[REDACTED]"
```

Or via env:

| Var | Default | Notes |
| --- | --- | --- |
| `BOTANU_PII_SCRUB_ENABLED` | `true` | Set to `false` to opt out |
| `BOTANU_PII_SCRUB_DISABLE_PATTERNS` | unset | Comma-separated names |
| `BOTANU_PII_SCRUB_USE_PRESIDIO` | `false` | Requires the `pii-nlp` extra |
| `BOTANU_PII_SCRUB_REPLACEMENT` | `[REDACTED]` | Any string |

### Presidio NER (optional)

For name/address/medical-term detection, install the optional extra:

```bash
pip install botanu[pii-nlp]
```

…and set `pii_scrub_use_presidio=true`. Without the package installed, the
flag is a no-op and the regex pass continues to run (you get a warning log
on first use). Entities covered: `EMAIL_ADDRESS`, `PHONE_NUMBER`,
`CREDIT_CARD`, `US_SSN`, `PERSON`, `LOCATION`, `IP_ADDRESS`,
`US_BANK_NUMBER`, `MEDICAL_LICENSE`.

### If you need stricter privacy

Keep `content_capture_rate=0.0` and drive eval off explicit tool/score
annotations instead. The capture pipeline is opt-in precisely so you can
stay private by default.

## Verifying capture is on

After setting a non-zero rate, run a workflow and check the span attributes
with your normal OTel tooling. A captured span will carry
`botanu.eval.input_content` and `botanu.eval.output_content` as string
attributes. If they are absent, check in order:

1. `BotanuConfig.content_capture_rate` is actually > 0.0 in the running
   process (`BotanuConfig.from_yaml(...)` and env precedence can surprise
   you — print `get_config().content_capture_rate` to be sure).
2. You are inside a span (`botanu.event` or `track_llm_call` scope).
3. The random gate didn't miss — at `rate=0.1`, ~90% of calls will look
   empty. Set the rate to `1.0` temporarily to confirm plumbing.

## See also

- [LLM Tracking → set_input_content / set_output_content](llm-tracking.md#set_input_content-set_output_content)
- [Configuration → content_capture_rate](../getting-started/configuration.md)
- `src/botanu/sampling/content_sampler.py` — the rate gate
- `src/botanu/sdk/decorators.py` — workflow-level auto-capture
- `src/botanu/tracking/llm.py` — LLM-span capture
