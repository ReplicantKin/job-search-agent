---
name: hr-communication
description: Draft transparent, human-reviewed HR messages from local job context without impersonation or automatic commitments.
---

# HR Communication

This skill is draft-first. It may summarize an incoming recruiter message and prepare a response, but it must not silently monitor a mailbox or send a message without explicit user authorization.

## First-contact disclosure

When the user approves a first-contact response, disclose that an AI assistant is helping organize the conversation and that the candidate will review important information.

Use the user's configured display name rather than a package default. A safe starting draft is: “你好，我是{display_name}授权的 AI 求职助手，正在协助整理这段沟通；{display_name}会亲自查看重要信息并回复。你现在想先了解哪些情况？” Treat this as a draft until the user approves the wording and channel.

## Always pause for

- Salary, start date, work location, relocation, visa, or working-hours commitments.
- Questions about confidential prior employers or customers.
- Claims not present in the approved profile or application materials.
- Any request to represent the candidate without explicit confirmation.

Keep the original incoming text, draft text, user decision, and final sent text as separate events when the surrounding integration supports message logging.

The local core provides a draft-first record without a sending integration:

```bash
python3 scripts/job_search_agent.py communication record JOB_ID \
  --channel boss --direction incoming --text-file recruiter-message.txt
python3 scripts/job_search_agent.py communication record JOB_ID \
  --channel boss --direction draft --text-file reply-draft.txt
python3 scripts/job_search_agent.py communication list JOB_ID --format json
```

Recording `--direction sent` requires `--user-confirmed`; this records a message the user has already sent and does not send it. Message records remain local and are included in explicit JSON exports.
