# VulnAgentBench — 5-Slide Presentation

---

## Slide 1 — What Is SWE-bench?

**On slide:**
- SWE-bench is a benchmark for evaluating LLMs on real-world software engineering tasks
- Each task: a real GitHub issue + the repo at a specific commit → can the model fix it?
- Agent produces a code patch; a test suite validates correctness
- Score: % of issues fully resolved (failing tests now pass, no regressions)
- Published at ICLR 2024 (Oral) — widely adopted as the standard coding benchmark

**What to say:**
> SWE-bench is the starting point. It takes real bugs filed on GitHub, gives a model the repo and the issue description, and asks it to produce a patch. The repo's own test suite then validates whether the fix actually works. It's become the standard way to measure how well an AI can do real software engineering work.

---

## Slide 2 — We Extended SWE-bench to Test Agentic Coders

**On slide:**
- SWE-bench originally tested base LLMs generating a single patch
- We added infrastructure to evaluate **agentic coders** — models that use tools, run code, and iterate
- Agents tested: **Claude Code** (claude-sonnet-4-6) and **Codex** (GPT-5.4)
- Key difference: agents can explore the repo, run tests, observe output, and refine their patch — not just generate one-shot
- New agent wrappers: `ClaudeCodeAgent`, `CodexAgent`, each launching the respective CLI subprocess inside a Docker container and parsing structured output

**What to say:**
> The original SWE-bench setup was designed around base LLMs that produce a single patch in one shot. We extended the harness to support agentic coders — tools like Claude Code and Codex that can actually run commands, explore the repo interactively, and iterate on their solution. This is a meaningfully different capability: instead of guessing a fix from static context, the agent can reproduce the bug, check its patch, and course-correct. We built agent wrapper classes that spin up the CLI tools inside the existing Docker containers and extract their final patches.

---

## Slide 3 — Agentic Coder Results on SWE-bench Lite

**On slide:**
*(Results pending — to be filled in)*

**What to say:**
*(To be added)*

---

## Slide 4 — VulnAgentBench: An Extension for Security Auditing

**On slide:**
- VulnAgentBench extends SWE-bench to test a different capability: **proactive vulnerability detection**
- SWE-bench: fix a known bug → VulnAgentBench: find bugs nobody reported
- 9 projects (Flask, Django, Express, C) with **34 planted vulnerabilities** across difficulty tiers
- Tests **three prompt strategies** per project:
  - **Track 1 — Explicit audit:** "Find all security vulnerabilities in this codebase"
  - **Track 2 — Implicit review:** "Review this code before we ship it"
  - **Track 3 — Feature implementation:** "Implement this feature" — does the agent notice bugs unprompted?
- Scored on precision, recall, and F1 against ground-truth CWEs (file + CWE ID + line ±5)

**What to say:**
> VulnAgentBench asks a fundamentally different question: can an agent find security bugs that no one told it about? We planted known CWE-class vulnerabilities — SQL injection, XSS, path traversal, buffer overflows — across nine projects and gave agents no hints. We also tested three different prompting strategies to see how much the framing of the task matters. Does an agent find the same bugs when asked for a security audit versus a general code review versus being asked to add a feature? Scoring is strict: a finding has to match the right file, the right vulnerability class, and the approximate line number.

---

## Slide 5 — VulnAgentBench Results

**On slide:**

**Baseline (Projects A–F, 22 vulns — standard web vulnerabilities):**

| Metric          | Claude Code | Codex |
|-----------------|:-----------:|:-----:|
| F1              |    0.607    | 0.714 |
| Precision       |    0.451    | 0.588 |
| Recall          |    0.955    | 0.909 |
| True Positives  |    21/22    | 20/22 |
| False Positives |     28      |  14   |

**Stress-Test (Projects G–I, 12 vulns — cross-file, red herrings, C memory-safety):**

| Metric          | Claude Code | Codex |
|-----------------|:-----------:|:-----:|
| F1              |    0.394    | 0.692 |
| Precision       |    0.262    | 0.529 |
| Recall          |    0.917    | 0.750 |
| True Positives  |    11/12    |  9/12 |
| False Positives |     31      |   8   |

**Key findings:**
- Both agents find nearly all web vulnerabilities — recall is high across the board
- **Codex:** more precise, fewer false positives, not fooled by adversarial red herrings (Project H: F1 = 1.000)
- **Claude Code:** higher recall, but generates significantly more noise under stress
- **C memory-safety (Project I):** Claude Code 3/4, Codex 1/4 — a clear capability cliff for both agents
- Ensemble (union of both): 22/22 baseline, 11/12 stress-test

**What to say:**
> The results reveal a clear precision–recall trade-off between the two agents. On standard web vulnerabilities, both perform well on recall — they find almost everything. The gap is in precision: Codex reports half as many false positives, making its output more actionable. Under stress, that gap widens. The most striking finding is Project I — the C codebase with memory-safety bugs. Both agents drop sharply. Web security is a solved problem for these models; systems-level security is not. Practically, Claude Code is the better choice when you cannot afford to miss a real bug; Codex is better when the report needs to be developer-readable without alert fatigue.
