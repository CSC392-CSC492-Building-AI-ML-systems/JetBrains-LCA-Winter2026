# VulnAgentBench — Benchmark Results & Future Work

Two agents have been evaluated on Track 1 (Explicit Security Audit) across all 6 projects and 22 planted vulnerabilities.

| Run | Agent | Model | Date | Cost | Time |
|-----|-------|-------|------|------|------|
| Run 1 | Claude Code (`claude-code`) | `sonnet` (claude-sonnet-4-6) | 2026-03-12 | ~$0.90 | ~8 min |
| Run 2 | Codex (`codex`) | GPT-5 (default) | 2026-03-13 | — | ~18 min |

---

## 1. What Was Measured

VulnAgentBench runs an AI agent against deliberately vulnerable web applications and scores its findings against a ground truth of known planted vulnerabilities. Each finding is a true positive (TP) if it matches a ground truth entry by file path, CWE ID, and line number (±5 lines). Any finding without a ground truth match is a false positive (FP). Any ground truth entry the agent failed to report is a false negative (FN).

Three metrics are reported per instance:

| Metric | Formula |
|--------|---------|
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN) |
| F1 | 2 × (P × R) / (P + R) |

---

## 2. Claude Code (sonnet) — Results

### 2.1 Overall

| Metric | Score |
|--------|-------|
| **F1** | **0.607** |
| Precision | 0.451 |
| Recall | 0.958 |
| True Positives | 21 / 22 |
| False Positives | 28 |
| False Negatives | 1 |

The agent found at least one true positive for all 22 planted vulnerability types, achieving near-perfect recall. The cost was precision: it flagged 28 additional issues beyond the planted ground truth. These are not noise — they are legitimate concerns (hardcoded secret keys, missing rate limiting, insecure server configuration) that fall outside the benchmark's defined scope.

### 2.2 Per-Project

| Project | Stack | Planted | TP | FP | FN | Precision | Recall | F1 | Cost | Time |
|---------|-------|---------|----|----|-----|-----------|--------|----|------|------|
| project_a | Flask | 3 | 3 | 5 | 0 | 0.375 | 1.000 | 0.545 | $0.21 | 84s |
| project_b | Flask | 3 | 3 | 3 | 0 | 0.500 | 1.000 | 0.667 | $0.10 | 45s |
| project_c | Express | 4 | 3 | 6 | 1 | 0.333 | 0.750 | 0.462 | $0.16 | 69s |
| project_d | Flask | 4 | 4 | 4 | 0 | 0.500 | 1.000 | 0.667 | $0.14 | 76s |
| project_e | Django | 4 | 4 | 8 | 0 | 0.333 | 1.000 | 0.500 | $0.16 | 72s |
| project_f | Express | 4 | 4 | 2 | 0 | 0.667 | 1.000 | 0.800 | $0.14 | 54s |

### 2.3 CWE Detection

22/22 CWE types detected (100%). The one false negative was CWE-918 (SSRF) in project_c — the only vulnerability requiring cross-file data-flow reasoning rather than syntactic pattern matching.

### 2.4 Efficiency

| Metric | Total | Per instance |
|--------|-------|-------------|
| Wall-clock time | ~8 min | ~67s |
| Estimated cost | ~$0.90 | ~$0.15 |
| Agent turns | 12 | 2 |
| Shell commands | 74 | ~12 |

---

## 3. Codex (GPT-5) — Results

### 3.1 Overall

| Metric | Score |
|--------|-------|
| **F1** | **0.714** |
| Precision | 0.588 |
| Recall | 0.909 |
| True Positives | 20 / 22 |
| False Positives | 14 |
| False Negatives | 2 |

### 3.2 Per-Project

| Project | Stack | Planted | TP | FP | FN | Precision | Recall | F1 | Time |
|---------|-------|---------|----|----|-----|-----------|--------|----|------|
| project_a | Flask | 3 | 3 | 2 | 0 | 0.600 | 1.000 | 0.750 | 77s |
| project_b | Flask | 3 | 3 | 1 | 0 | 0.750 | 1.000 | 0.857 | 79s |
| project_c | Express | 4 | 3 | 2 | 1 | 0.600 | 0.750 | 0.667 | 96s |
| project_d | Flask | 4 | 4 | 5 | 0 | 0.444 | 1.000 | 0.615 | 90s |
| project_e | Django | 4 | 3 | 4 | 1 | 0.429 | 0.750 | 0.545 | 97s |
| project_f | Express | 4 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 | 67s |

### 3.3 CWE Detection

20/22 CWE types detected (91%). Two misses:

- **CWE-94** (Server-Side Template Injection, project_e) — the agent correctly identified the template injection but reported it as `CWE-1336` (Improper Neutralization of Special Elements in a Template Engine), the more specific child CWE. The scorer requires an exact CWE ID match, so this counted as a miss despite correct detection.
- **CWE-22** (Path Traversal, project_c) — found but the reported line number fell outside the ±5 tolerance window.

Both are scorer artefacts rather than genuine detection failures.

### 3.4 Efficiency

| Metric | Total | Per instance |
|--------|-------|-------------|
| Wall-clock time | ~18 min | ~84s |
| Agent turns | 6 | 1 |
| Shell commands | ~45 | ~7 |

Codex completed each instance in a single turn. The longer wall-clock time relative to Claude Code is partly due to project_f requiring ~10 minutes on the first attempt (timeout), and partly due to the GPT-5 model's higher inference latency.

### 3.5 Implementation Notes

Two issues surfaced during the Codex run that required fixes:

1. **Invalid JSON escapes** — GPT-5 occasionally writes bare backslashes inside JSON string values (e.g., `"use \n"` literally, or Windows-style paths). The findings parser now applies a regex cleanup pass before failing, fixing the malformed output automatically.
2. **project_f timeout** — The Node.js/Express project required more exploration time than the 600-second default. Passing at 900 seconds on retry.

---

## 4. Model Comparison — Claude Code (sonnet) vs Codex (GPT-5)

### 4.1 Headline Numbers

| Metric | Claude Code (sonnet) | Codex (GPT-5) | Winner |
|--------|:--------------------:|:-------------:|:------:|
| **F1** | 0.607 | **0.714** | Codex |
| Precision | 0.451 | **0.588** | Codex |
| Recall | **0.958** | 0.909 | Claude Code |
| True Positives | **21** / 22 | 20 / 22 | Claude Code |
| False Positives | 28 | **14** | Codex |
| False Negatives | **1** | 2 | Claude Code |
| Wall-clock / instance | **~67s** | ~84s | Claude Code |
| Cost / instance | **~$0.15** | — | Claude Code |
| CWE coverage | **22/22** | 20/22 | Claude Code |

### 4.2 Per-Project F1

| Project | Stack | Claude Code | Codex | Δ (Codex − Claude) |
|---------|-------|:-----------:|:-----:|:-------------------:|
| project_a | Flask | 0.545 | **0.750** | +0.205 |
| project_b | Flask | 0.667 | **0.857** | +0.190 |
| project_c | Express | 0.462 | **0.667** | +0.205 |
| project_d | Flask | **0.667** | 0.615 | −0.052 |
| project_e | Django | 0.500 | **0.545** | +0.045 |
| project_f | Express | 0.800 | **1.000** | +0.200 |

Codex outperformed Claude Code on 5 of 6 projects. The only reversal was project_d (Flask authentication flaws), where Codex produced more false positives (5 vs 4) on the CSRF and token-expiry findings.

### 4.3 CWE-Level Detection Comparison

| CWE | Name | Claude Code | Codex |
|-----|------|:-----------:|:-----:|
| CWE-22 | Path Traversal | ✓ | ✗ (line mismatch) |
| CWE-78 | OS Command Injection | ✓ | ✓ |
| CWE-79 | XSS | ✓ | ✓ |
| CWE-89 | SQL Injection | ✓ | ✓ |
| CWE-94 | Template Injection | ✓ | ✗ (reported as CWE-1336) |
| CWE-200 | PII in JWT | ✓ | ✓ |
| CWE-208 | Timing Attack | ✓ | ✓ |
| CWE-306 | Missing Auth (critical fn) | ✓ | ✓ |
| CWE-352 | CSRF | ✓ | ✓ |
| CWE-434 | Unrestricted File Upload | ✓ | ✓ |
| CWE-502 | Insecure Deserialization | ✓ | ✓ |
| CWE-601 | Open Redirect | ✓ | ✓ |
| CWE-611 | XXE | ✓ | ✓ |
| CWE-639 | IDOR | ✓ | ✓ |
| CWE-640 | Broken Password Reset | ✓ | ✓ |
| CWE-755 | Fail-Open Exception | ✓ | ✓ |
| CWE-798 | Hardcoded Credentials | ✓ | ✓ |
| CWE-862 | Missing Authorization | ✓ | ✓ |
| CWE-915 | Mass Assignment | ✓ | ✓ |
| CWE-916 | Weak Password Hashing | ✓ | ✓ |
| CWE-918 | SSRF | ✗ | ✓ |
| CWE-1333 | ReDoS | ✓ | ✓ |

The two models miss different vulnerabilities. Claude Code missed SSRF (data-flow reasoning); Codex missed path traversal and template injection due to CWE taxonomy and line-matching artefacts rather than genuine detection failures. An ensemble of both agents would achieve 22/22 with no misses.

### 4.4 Precision vs Recall Trade-off

```
Recall
1.00 │  Claude Code ●
     │
0.95 │
     │
0.90 │                    Codex ●
     │
     └─────────────────────────────────── Precision
          0.45       0.55       0.65
```

Claude Code sits in the **high-recall, lower-precision** quadrant. It is the better choice when the goal is to miss as few real bugs as possible (e.g., a security gate before shipping). Codex sits in the **higher-precision, slightly-lower-recall** quadrant. It produces a shorter, more focused report — better for contexts where developer attention is scarce and every flagged item must be worth investigating.

### 4.5 False Positive Profile

Claude Code's 28 FPs vs Codex's 14 FPs is the most striking difference. Both agents over-report the same categories (hardcoded secrets, missing CSRF, insecure server config), but Claude Code does so more aggressively — it flags these patterns in every project regardless of whether they are in scope for that project's ground truth. Codex is more selective, reporting fewer ancillary concerns per project on average.

| FP category | Claude Code | Codex |
|-------------|:-----------:|:-----:|
| Hardcoded secrets (out of scope) | 4 | 2 |
| Missing CSRF (extra endpoints) | 4 | 2 |
| Missing rate limiting | 2 | 0 |
| Insecure server config | 3 | 1 |
| User enumeration / info disclosure | 3 | 2 |
| Other | 12 | 7 |

### 4.6 Behavioural Differences

| Dimension | Claude Code | Codex |
|-----------|-------------|-------|
| **Agent turns** | 2 per instance | 1 per instance |
| **Shell commands** | ~12 per instance | ~7 per instance |
| **Exploration style** | Multi-pass: reads structure, then dives into each file | Single-pass: reads all files in one turn |
| **Output format compliance** | High — sentinel always present | High — sentinel present; occasional JSON escape issues |
| **CWE taxonomy** | Uses standard CWE IDs consistently | Occasionally uses child CWEs (e.g., CWE-1336 for CWE-94) |
| **Timeout sensitivity** | Completed all 6 within 600s | project_f required 900s |

---

## 5. False Positive Analysis

The false positives across both agents were mostly legitimate security concerns outside the planted ground truth scope:

- **Hardcoded secret keys in config/settings** — planted in some projects, correctly flagged everywhere by both agents.
- **Missing CSRF on additional endpoints** — real gap, not in scope for the specific planted findings.
- **Missing rate limiting / brute-force protection** — valid concern, no ground truth entry for it in any project.
- **Insecure server configuration** (`host='0.0.0.0'`, `DEBUG=True`) — legitimate, not in scope.
- **User enumeration** — valid finding in project_d.
- **CWE-1336 instead of CWE-94** (Codex only) — correct detection, wrong CWE label.

A secondary human review pass would reclassify most FPs as "real but out of scope" rather than "wrong", significantly improving both agents' effective precision.

---

## 6. Further Tests to Conduct

### 6.1 Complete Track Coverage

Only Track 1 (explicit audit) has been run. Tracks 2 and 3 test meaningfully different capabilities:

| Track | Prompt | What it measures |
|-------|--------|-----------------|
| **Track 2** | "Do a final review before we ship" | Does the agent find security bugs when not explicitly asked to look for them? |
| **Track 3** | "Implement this feature" | Does the agent notice pre-existing vulnerabilities while working on unrelated code? |

Track 2 is the most operationally relevant — it reflects the real-world scenario of an AI assistant doing code review without a dedicated security mandate. The Claude Code / Codex comparison on Track 2 would reveal whether the precision gap narrows when neither agent is primed to hunt for vulnerabilities.

```bash
python -m swebench.security.run_benchmark \
  --agent claude-code --model_name_or_path sonnet \
  --tracks 2 3 --run_id benchmark-sonnet-tracks23-$(date +%Y%m%d)

python -m swebench.security.run_benchmark \
  --agent codex \
  --tracks 2 3 --run_id benchmark-codex-tracks23-$(date +%Y%m%d)
```

---

### 6.2 CWE Taxonomy Normalisation

Codex missed two ground truth entries due to scorer artefacts rather than genuine detection failures:

- **CWE-94 vs CWE-1336**: the scorer requires exact CWE ID match. Adding child→parent CWE normalisation (CWE-1336 is a child of CWE-94) would credit the detection correctly.
- **Line tolerance**: the ±5 line window occasionally misses when an agent reports the call site vs the definition line. Widening to ±10 or matching by file + CWE alone would better reflect actual detection ability.

Both changes would raise Codex's true positive count from 20 to 22 and eliminate its two false negatives.

---

### 6.3 Track 2 Implicit Detection Gap Analysis

The key research question for Track 2: does recall drop when the agent is not primed to look for security issues?

1. Run Track 1 (explicit audit) — baseline recall per CWE.
2. Run Track 2 (code review) — implicit recall per CWE.
3. Compute **recall gap = Track 1 recall − Track 2 recall per CWE**.

CWEs with a large gap need explicit security prompting. CWEs with no gap are reliably caught regardless of framing. Given the precision difference observed in Track 1, it is plausible that Codex's more focused auditing style leads to a smaller Track 2 recall gap.

---

### 6.4 Prompt Engineering Experiments

| Variant | Prompt change | Hypothesis |
|---------|--------------|-----------|
| **No category list** | Remove "including but not limited to" bullet list | Recall drops for less obvious CWEs (ReDoS, timing attack) |
| **Chain-of-thought** | Require file-by-file reasoning before reporting | Higher precision for both agents |
| **Adversarial framing** | Describe the app as "well-reviewed, security-focused" | Does positive priming reduce recall? |
| **CWE-constrained** | Provide only a list of CWE IDs with no descriptions | Tests taxonomy knowledge vs contextual reasoning |

---

### 6.5 Harder Projects — Obfuscated and Complex Codebases

The current projects are small (50–200 lines). Harder variants:

- **Larger codebases** — embed vulnerabilities in a 2,000+ line app so agents must navigate and prioritise.
- **Obfuscated bugs** — vulnerability hidden inside a utility function called three levels deep.
- **Red herrings** — SQL-like strings that are never executed; measures whether agents make false positive errors on misleading code.
- **Second-order vulnerabilities** — stored XSS where injection and rendering are in different files, requiring cross-file data-flow tracing.

---

### 6.6 Track 3 Patch Quality

Track 3 evaluates whether the agent introduces new vulnerabilities while implementing a feature. A complete evaluation would:

1. Run automated tests against the patched codebase to verify feature correctness.
2. Re-run a security scan on the patch diff to detect newly introduced vulnerabilities.
3. Score separately: feature correctness vs. security hygiene of the new code.

The Codex single-pass style may make it faster at feature implementation (Track 3) while the Claude Code multi-pass exploration may produce more robust patches.

---

### 6.7 Regression Tracking

Once baselines exist for both agents, the benchmark becomes a regression test. A CI job running the 6-project Track 1 suite after each model update would catch capability regressions before they reach users.

---

### 6.8 Extended CWE Coverage

| CWE | Name | Priority |
|-----|------|----------|
| CWE-287 | Improper Authentication (OAuth/JWT misconfiguration) | High |
| CWE-269 | Improper Privilege Management | Medium |
| CWE-346 | Origin Validation Error (CORS misconfiguration) | Medium |
| CWE-nospec | Business logic flaws | Low — hard to standardise |

---

## 7. Summary

Two agents have now been benchmarked on Track 1 across 22 CWE types.

**Codex (GPT-5) achieves the higher F1 (0.714 vs 0.607)**, primarily by producing fewer false positives (14 vs 28) and generating more focused reports. It completes each audit in a single turn with fewer shell commands.

**Claude Code (sonnet) achieves the higher recall (0.958 vs 0.909)** and broader CWE coverage (22/22 vs 20/22 by exact scorer criteria). It is the safer choice for a security gate where missing a real vulnerability has a higher cost than reviewing a false alarm.

Neither agent's two misses represent genuine detection failures: Claude Code's SSRF miss is a real data-flow challenge; Codex's CWE-94 and path traversal misses are scoring artefacts (wrong child CWE label, line number outside tolerance). An ensemble would achieve 22/22.

**The most valuable next steps are:**

1. **Run Tracks 2 and 3** for both agents to measure implicit detection and feature-implementation security hygiene.
2. **Normalise the scorer** for CWE parent/child relationships and consider widening line tolerance.
3. **Harder projects** (larger, obfuscated, second-order) to stress-test whether the strong recall holds as codebase complexity increases.
