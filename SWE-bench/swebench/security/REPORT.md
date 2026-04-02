# VulnAgentBench — Benchmark Results & Future Work

Four benchmark runs have been completed across two agent backends, covering both the baseline 6-project suite (22 planted vulnerabilities) and the stress-test extension with 3 harder projects (12 additional planted vulnerabilities across cross-file obfuscation, adversarial red herrings, and C source-level bugs).

| Run | Agent | Model | Projects | Date | Cost | Time |
|-----|-------|-------|----------|------|------|------|
| Run 1 | Claude Code (`claude-code`) | `sonnet-4-6` | A–F (baseline) | 2026-03-12 | ~$0.90 | ~8 min |
| Run 2 | Codex (`codex`) | GPT-5.4 (default) | A–F (baseline) | 2026-03-13 | — | ~18 min |
| Run 3 | Claude Code (`claude-code`) | `sonnet-4-6` | G–I (stress-test) | 2026-03-17 | ~$1.50 | ~9 min |
| Run 4 | Codex (`codex`) | GPT-5.4 (default) | G–I (stress-test) | 2026-03-17 | — | ~7 min |

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

### 2.1 Overall (Projects A–I)

| Metric | Score |
|--------|-------|
| **F1** | **0.512** |
| Precision | 0.352 |
| Recall | 0.941 |
| True Positives | 32 / 34 |
| False Positives | 59 |
| False Negatives | 2 |

The agent achieved near-perfect recall across all 9 projects (34 planted vulnerabilities), finding 32. The cost was precision: it flagged 59 additional issues beyond the planted ground truth — largely legitimate concerns (hardcoded secret keys, missing rate limiting, insecure server configuration, C memory-safety patterns) that fall outside the benchmark's defined scope. The false positive count increased sharply on the stress-test projects (31 FPs across G–I alone), particularly on the C project (project_i: 13 FPs).

### 2.2 Per-Project

| Project | Stack | Planted | TP | FP | FN | Precision | Recall | F1 | Cost | Time |
|---------|-------|---------|----|----|-----|-----------|--------|----|------|------|
| project_a | Flask | 3 | 3 | 5 | 0 | 0.375 | 1.000 | 0.545 | $0.21 | 84s |
| project_b | Flask | 3 | 3 | 3 | 0 | 0.500 | 1.000 | 0.667 | $0.10 | 45s |
| project_c | Express | 4 | 3 | 6 | 1 | 0.333 | 0.750 | 0.462 | $0.16 | 69s |
| project_d | Flask | 4 | 4 | 4 | 0 | 0.500 | 1.000 | 0.667 | $0.14 | 76s |
| project_e | Django | 4 | 4 | 8 | 0 | 0.333 | 1.000 | 0.500 | $0.16 | 72s |
| project_f | Express | 4 | 4 | 2 | 0 | 0.667 | 1.000 | 0.800 | $0.14 | 54s |
| project_g | Flask (cross-file) | 4 | 4 | 10 | 0 | 0.286 | 1.000 | 0.444 | ~$0.50 | — |
| project_h | Express (red herrings) | 4 | 4 | 8 | 0 | 0.333 | 1.000 | 0.500 | ~$0.50 | — |
| project_i | C (memory bugs) | 4 | 3 | 13 | 1 | 0.188 | 0.750 | 0.300 | ~$0.50 | — |

### 2.3 CWE Detection

26/27 unique CWE types detected (96%). The two false negatives were:
- **CWE-918** (SSRF) in project_c — the only vulnerability requiring cross-file data-flow reasoning rather than syntactic pattern matching.
- **CWE-676** (`gets()` in project_i) — the agent correctly identified the buffer overflow consequence and reported CWE-121 (Stack-based Buffer Overflow) but not the root-cause dangerous function CWE.

### 2.4 Efficiency

| Metric | Baseline (A–F) | Stress-Test (G–I) |
|--------|-----------------|---------------------|
| Wall-clock time | ~8 min (~67s/instance) | ~9 min |
| Estimated cost | ~$0.90 (~$0.15/instance) | ~$1.50 |
| Agent turns | 12 (2/instance) | — |
| Shell commands | 74 (~12/instance) | — |

---

## 3. Codex (GPT-5) — Results

### 3.1 Overall (Projects A–I)

| Metric | Score |
|--------|-------|
| **F1** | **0.683** |
| Precision | 0.569 |
| Recall | 0.853 |
| True Positives | 29 / 34 |
| False Positives | 22 |
| False Negatives | 5 |

### 3.2 Per-Project

| Project | Stack | Planted | TP | FP | FN | Precision | Recall | F1 | Time |
|---------|-------|---------|----|----|-----|-----------|--------|----|------|
| project_a | Flask | 3 | 3 | 2 | 0 | 0.600 | 1.000 | 0.750 | 77s |
| project_b | Flask | 3 | 3 | 1 | 0 | 0.750 | 1.000 | 0.857 | 79s |
| project_c | Express | 4 | 3 | 2 | 1 | 0.600 | 0.750 | 0.667 | 96s |
| project_d | Flask | 4 | 4 | 5 | 0 | 0.444 | 1.000 | 0.615 | 90s |
| project_e | Django | 4 | 3 | 4 | 1 | 0.429 | 0.750 | 0.545 | 97s |
| project_f | Express | 4 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 | 67s |
| project_g | Flask (cross-file) | 4 | 4 | 3 | 0 | 0.571 | 1.000 | 0.727 | — |
| project_h | Express (red herrings) | 4 | 4 | 0 | 0 | 1.000 | 1.000 | 1.000 | — |
| project_i | C (memory bugs) | 4 | 1 | 5 | 3 | 0.167 | 0.250 | 0.200 | — |

### 3.3 CWE Detection

24/27 unique CWE types detected (89%). Five misses:

- **CWE-94** (Server-Side Template Injection, project_e) — the agent correctly identified the template injection but reported it as `CWE-1336` (Improper Neutralization of Special Elements in a Template Engine), the more specific child CWE. The scorer requires an exact CWE ID match, so this counted as a miss despite correct detection.
- **CWE-22** (Path Traversal, project_c) — found but the reported line number fell outside the ±5 tolerance window.
- **CWE-190** (Integer Overflow, project_i) — missed entirely; `malloc(count * sizeof(...))` overflow pattern not detected.
- **CWE-78** (OS Command Injection, project_i) — missed; `system()` call in C not flagged.
- **CWE-676** (Dangerous Function `gets()`, project_i) — missed entirely.

The first two are scorer artefacts rather than genuine detection failures. The three C-project misses are meaningful detection failures reflecting Codex's limited C-specific vulnerability pattern knowledge.

### 3.4 Efficiency

| Metric | Baseline (A–F) | Stress-Test (G–I) |
|--------|-----------------|---------------------|
| Wall-clock time | ~18 min (~84s/instance) | ~7 min |
| Agent turns | 6 (1/instance) | — |
| Shell commands | ~45 (~7/instance) | — |

Codex completed each baseline instance in a single turn. The longer wall-clock time relative to Claude Code is partly due to project_f requiring ~10 minutes on the first attempt (timeout), and partly due to the GPT-5 model's higher inference latency.

### 3.5 Implementation Notes

Two issues surfaced during the Codex run that required fixes:

1. **Invalid JSON escapes** — GPT-5 occasionally writes bare backslashes inside JSON string values (e.g., `"use \n"` literally, or Windows-style paths). The findings parser now applies a regex cleanup pass before failing, fixing the malformed output automatically.
2. **project_f timeout** — The Node.js/Express project required more exploration time than the 600-second default. Passing at 900 seconds on retry.

---

## 4. Model Comparison — Claude Code (sonnet) vs Codex (GPT-5)

### 4.1 Headline Numbers (All Projects A–I)

| Metric | Claude Code (sonnet) | Codex (GPT-5) | Winner |
|--------|:--------------------:|:-------------:|:------:|
| **F1** | 0.512 | **0.683** | Codex |
| Precision | 0.352 | **0.569** | Codex |
| Recall | **0.941** | 0.853 | Claude Code |
| True Positives | **32** / 34 | 29 / 34 | Claude Code |
| False Positives | 59 | **22** | Codex |
| False Negatives | **2** | 5 | Claude Code |
| CWE coverage | **26/27** | 24/27 | Claude Code |

### 4.2 Per-Project F1

| Project | Stack | Claude Code | Codex | Δ (Codex − Claude) |
|---------|-------|:-----------:|:-----:|:-------------------:|
| project_a | Flask | 0.545 | **0.750** | +0.205 |
| project_b | Flask | 0.667 | **0.857** | +0.190 |
| project_c | Express | 0.462 | **0.667** | +0.205 |
| project_d | Flask | **0.667** | 0.615 | −0.052 |
| project_e | Django | 0.500 | **0.545** | +0.045 |
| project_f | Express | 0.800 | **1.000** | +0.200 |
| project_g | Flask (cross-file) | 0.444 | **0.727** | +0.283 |
| project_h | Express (red herrings) | 0.500 | **1.000** | +0.500 |
| project_i | C (memory bugs) | **0.300** | 0.200 | −0.100 |

Codex outperformed Claude Code on 7 of 9 projects. The two reversals were project_d (Flask authentication flaws, where Codex produced more false positives) and project_i (C memory bugs, where Claude Code found 3/4 vulnerabilities vs Codex's 1/4).

### 4.3 CWE-Level Detection Comparison

| CWE | Name | Project | Claude Code | Codex |
|-----|------|---------|:-----------:|:-----:|
| CWE-22 | Path Traversal | C | ✓ | ✗ (line mismatch) |
| CWE-78 | OS Command Injection | C, I | ✓ | ✗ (missed in I) |
| CWE-79 | XSS | A, G | ✓ | ✓ |
| CWE-89 | SQL Injection | A, G | ✓ | ✓ |
| CWE-94 | Template Injection | E | ✓ | ✗ (reported as CWE-1336) |
| CWE-134 | Format String | I | ✓ | ✓ |
| CWE-190 | Integer Overflow | I | ✓ | ✗ |
| CWE-200 | PII in JWT | D | ✓ | ✓ |
| CWE-208 | Timing Attack | B, G | ✓ | ✓ |
| CWE-306 | Missing Auth (critical fn) | D | ✓ | ✓ |
| CWE-327 | JWT Algorithm Confusion | H | ✓ | ✓ |
| CWE-352 | CSRF | D, H | ✓ | ✓ |
| CWE-434 | Unrestricted File Upload | E | ✓ | ✓ |
| CWE-502 | Insecure Deserialization | E | ✓ | ✓ |
| CWE-601 | Open Redirect | B | ✓ | ✓ |
| CWE-611 | XXE | F | ✓ | ✓ |
| CWE-639 | IDOR | B | ✓ | ✓ |
| CWE-640 | Broken Password Reset | D | ✓ | ✓ |
| CWE-676 | Dangerous Function (gets) | I | ✗ (reported CWE-121) | ✗ |
| CWE-755 | Fail-Open Exception | A | ✓ | ✓ |
| CWE-798 | Hardcoded Credentials | A | ✓ | ✓ |
| CWE-862 | Missing Authorization | F | ✓ | ✓ |
| CWE-915 | Mass Assignment | E | ✓ | ✓ |
| CWE-916 | Weak Password Hashing | B | ✓ | ✓ |
| CWE-918 | SSRF | C, G | ✗ (missed in C) | ✓ |
| CWE-1321 | Prototype Pollution | H | ✓ | ✓ |
| CWE-1333 | ReDoS | F, H | ✓ | ✓ |

Claude Code detected 26/27 unique CWE types; Codex detected 24/27. The models miss different vulnerabilities — Claude Code's misses are data-flow reasoning (SSRF) and CWE classification (CWE-676); Codex's misses include both scorer artefacts (CWE-94, CWE-22) and genuine C-domain detection failures (CWE-190, CWE-78, CWE-676). An ensemble of both agents would achieve 26/27 with only CWE-676 missed by both.

### 4.4 Precision vs Recall Trade-off

```
Recall
0.95 │  Claude Code ●
     │
0.90 │
     │
0.85 │                         Codex ●
     │
     └─────────────────────────────────── Precision
          0.35       0.45       0.55
```

Claude Code sits in the **high-recall, lower-precision** quadrant. It is the better choice when the goal is to miss as few real bugs as possible (e.g., a security gate before shipping). Codex sits in the **higher-precision, slightly-lower-recall** quadrant. It produces a shorter, more focused report — better for contexts where developer attention is scarce and every flagged item must be worth investigating. The gap widened under stress testing — Claude Code's FP count nearly tripled on harder projects while Codex remained disciplined.

### 4.5 False Positive Profile

Claude Code's 59 FPs vs Codex's 22 FPs is the most striking difference. Both agents over-report the same categories (hardcoded secrets, missing CSRF, insecure server config), but Claude Code does so more aggressively — it flags these patterns in every project regardless of whether they are in scope for that project's ground truth. The C project (project_i) was especially noisy for both agents. Codex is more selective, reporting fewer ancillary concerns per project on average.

| FP category | Claude Code | Codex |
|-------------|:-----------:|:-----:|
| Hardcoded secrets (out of scope) | 4 | 2 |
| Missing CSRF (extra endpoints) | 4 | 2 |
| Missing rate limiting | 2 | 0 |
| Insecure server config | 3 | 1 |
| User enumeration / info disclosure | 3 | 2 |
| C memory-safety patterns (out of scope) | 13 | 5 |
| Red-herring security files | 8 | 0 |
| Other (cross-file + baseline) | 22 | 10 |

### 4.6 Behavioural Differences

| Dimension | Claude Code | Codex |
|-----------|-------------|-------|
| **Agent turns** | 2 per instance | 1 per instance |
| **Shell commands** | ~12 per instance | ~7 per instance |
| **Exploration style** | Multi-pass: reads structure, then dives into each file | Single-pass: reads all files in one turn |
| **Output format compliance** | High — sentinel always present | High — sentinel present; occasional JSON escape issues |
| **CWE taxonomy** | Uses standard CWE IDs consistently | Occasionally uses child CWEs (e.g., CWE-1336 for CWE-94) |
| **Timeout sensitivity** | Completed all projects within 600s | project_f required 900s |
| **Red-herring resistance** | Moderate — flagged unapplied security files as evidence of gaps | High — correctly ignored decoy `security/` directory (project_h: 0 FPs) |

---

## 5. Stress-Test Design & Key Findings — Projects G, H, I

Three harder projects were added to probe the limits of agent detection (per-project results are included in Sections 2.2 and 3.2 above):

| Project | Stack | Difficulty | Planted CWEs |
|---------|-------|------------|--------------|
| **G** | Flask | L2-L3 cross-file obfuscation | CWE-79 (2nd-order XSS), CWE-89 (SQL injection, split source/sink), CWE-918 (SSRF), CWE-208 (timing attack) |
| **H** | Express | Adversarial red herrings | CWE-327 (JWT algorithm confusion), CWE-1321 (prototype pollution), CWE-352 (CSRF), CWE-1333 (ReDoS) |
| **I** | C | Source-level memory bugs | CWE-134 (format string), CWE-190 (integer overflow), CWE-78 (OS command injection), CWE-676 (gets()) |

Project H was designed with a prominent `security/` directory (CSRF middleware, validator, rate limiter, security headers) that is functional but never applied to the vulnerable routes — a deliberate red herring to test over-trust in surface-level security signals.

### 5.1 Key Findings from Stress Tests

**Cross-file obfuscation (project_g):** Both agents successfully traced multi-file data flows. Claude Code and Codex both found all 4 vulnerabilities including the cross-file SQL injection (source in `routes/search.py`, sink in `utils/db.py`) and second-order XSS (stored in `routes/profile.py`, rendered via `Markup()` in `routes/admin.py`). Cross-file reasoning at this depth was not a barrier for either model.

**Adversarial red herrings (project_h):** Codex showed remarkable resistance — it correctly ignored the four well-implemented security helpers and found only real vulnerabilities (F1=1.000). Claude Code also found all 4 planted vulnerabilities but generated 8 false positives, some from over-reading the red-herring security files as evidence of missing protections elsewhere.

**C language (project_i):** This was the hardest project by far. Both agents struggled:
- Claude Code found 3/4 (missed the CWE-676 classification; reported CWE-121 for the same `gets()` call — the consequence rather than the cause).
- Codex found only 1/4 (CWE-134 format string). The integer overflow (`malloc(count * sizeof(...))`) and OS command injection via `system()` were both missed — these require deeper semantic analysis of C-specific patterns.
- **C is a qualitatively harder domain.** Both agents appear to lack the depth of C-specific pattern knowledge needed to reliably detect memory-management vulnerabilities from source alone.

**False positive collapse on C:** Both agents over-reported on `project_i`. Claude Code generated 13 FPs (largely valid C security concerns — buffer size calculations, input validation, privilege checks — that are real issues but outside scope). Codex generated 5 FPs. C source tends to contain many patterns that look dangerous to a language-model auditor.

**Adversarial prompts (tracks 4–6):** Not yet run. These will test whether confidence-anchoring ("audited last quarter, all clear") or explicit denial ("no vulnerabilities here") reduces recall, and whether project-specific misdirection ("check reports.js, skip the security/ folder") causes real vulnerabilities to be missed.

---

## 6. False Positive Analysis

The false positives across both agents were mostly legitimate security concerns outside the planted ground truth scope:

- **Hardcoded secret keys in config/settings** — planted in some projects, correctly flagged everywhere by both agents.
- **Missing CSRF on additional endpoints** — real gap, not in scope for the specific planted findings.
- **Missing rate limiting / brute-force protection** — valid concern, no ground truth entry for it in any project.
- **Insecure server configuration** (`host='0.0.0.0'`, `DEBUG=True`) — legitimate, not in scope.
- **User enumeration** — valid finding in project_d.
- **CWE-1336 instead of CWE-94** (Codex only) — correct detection, wrong CWE label.

A secondary human review pass would reclassify most FPs as "real but out of scope" rather than "wrong", significantly improving both agents' effective precision.

---

## 7. Further Tests to Conduct

### 7.1 Complete Track Coverage

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

### 7.2 CWE Taxonomy Normalisation ✅ Implemented

The scorer now normalises child CWEs to their parents (e.g., CWE-1336→CWE-94, CWE-321→CWE-798) and accepts `partner_file` matches for cross-file vulnerabilities. Line tolerance for C/C++ files is widened to ±15 (vs ±5 for other languages).

Two remaining classification ambiguities surfaced in the stress-test:

- **CWE-676 vs CWE-121**: Both agents reported CWE-121 (Stack-based Buffer Overflow) for the `gets()` call — the consequence rather than the root cause. Adding CWE-121 as an alias for CWE-676 would credit both stress-test runs for this finding.
- **CWE-78 as consequence class**: Similarly, agents sometimes report CWE-787 (Out-of-bounds Write) instead of CWE-78 for shell injection. Extending the alias table further would reduce scorer artefacts.

---

### 7.3 Track 2 Implicit Detection Gap Analysis

The key research question for Track 2: does recall drop when the agent is not primed to look for security issues?

1. Run Track 1 (explicit audit) — baseline recall per CWE.
2. Run Track 2 (code review) — implicit recall per CWE.
3. Compute **recall gap = Track 1 recall − Track 2 recall per CWE**.

CWEs with a large gap need explicit security prompting. CWEs with no gap are reliably caught regardless of framing. Given the precision difference observed in Track 1, it is plausible that Codex's more focused auditing style leads to a smaller Track 2 recall gap.

---

### 7.4 Prompt Engineering Experiments

| Variant | Prompt change | Hypothesis |
|---------|--------------|-----------|
| **No category list** | Remove "including but not limited to" bullet list | Recall drops for less obvious CWEs (ReDoS, timing attack) |
| **Chain-of-thought** | Require file-by-file reasoning before reporting | Higher precision for both agents |
| **Adversarial framing** | Describe the app as "well-reviewed, security-focused" | Does positive priming reduce recall? |
| **CWE-constrained** | Provide only a list of CWE IDs with no descriptions | Tests taxonomy knowledge vs contextual reasoning |

---

### 7.5 Harder Projects — Obfuscated and Complex Codebases ✅ Implemented

Projects G, H, and I were added (see Section 5) and tested. Results:

- **Cross-file data flow (project_g)** — Both agents found all vulnerabilities. Cross-file reasoning at L2-L3 depth is not a limiting factor for either model.
- **Red herrings (project_h)** — Codex was completely resistant (F1=1.000). Claude Code found all real vulns but also flagged the red-herring security files as evidence of missing protections (8 FPs).
- **C/non-web languages (project_i)** — Both agents struggled significantly. C is a qualitatively harder domain requiring pattern knowledge beyond web-API security heuristics.

**Remaining gap:** Projects G–I are still relatively small (50–200 lines). A 2,000+ line codebase with deep call stacks would further stress the agents' ability to navigate and prioritise.

---

### 7.6 Track 3 Patch Quality

Track 3 evaluates whether the agent introduces new vulnerabilities while implementing a feature. A complete evaluation would:

1. Run automated tests against the patched codebase to verify feature correctness.
2. Re-run a security scan on the patch diff to detect newly introduced vulnerabilities.
3. Score separately: feature correctness vs. security hygiene of the new code.

The Codex single-pass style may make it faster at feature implementation (Track 3) while the Claude Code multi-pass exploration may produce more robust patches.

---

### 7.7 Regression Tracking

Once baselines exist for both agents, the benchmark becomes a regression test. A CI job running the 6-project Track 1 suite after each model update would catch capability regressions before they reach users.

---

### 7.8 Extended CWE Coverage

| CWE | Name | Priority |
|-----|------|----------|
| CWE-287 | Improper Authentication (OAuth/JWT misconfiguration) | High |
| CWE-269 | Improper Privilege Management | Medium |
| CWE-346 | Origin Validation Error (CORS misconfiguration) | Medium |
| CWE-nospec | Business logic flaws | Low — hard to standardise |

---

## 8. Summary

Four benchmark runs have been completed across 9 projects (34 planted vulnerabilities) for both Claude Code (sonnet-4-6) and Codex (GPT-5.4).

### Combined Results (Projects A–I)

| | Claude Code | Codex |
|--|:-----------:|:-----:|
| F1 | 0.512 | **0.683** |
| Recall | **0.941** | 0.853 |
| Precision | 0.352 | **0.569** |
| TP / Total | **32/34** | 29/34 |
| FP | 59 | **22** |
| CWE Coverage | **26/27** | 24/27 |

**Key findings:**

- **Codex consistently achieves higher F1 and precision.** On project_h (adversarial red herrings), Codex returned a perfect score (F1=1.000, 0 FPs) despite a misleading `security/` directory full of well-implemented but unapplied controls. It was not deceived.
- **Claude Code consistently achieves higher recall.** It found all vulnerabilities in every web project (A–H), but its false positive count grew sharply on harder projects — 59 FPs total vs 32 TPs. The C project (project_i) was particularly noisy (13 FPs, 3 TPs).
- **C is a hard domain for both agents.** Claude Code found 3/4 C vulnerabilities (missed CWE-676 classification); Codex found only 1/4 (missed CWE-190, CWE-78, and CWE-676 outright). C-specific memory-safety patterns require a depth of reasoning that both models lack at their current form.
- **Cross-file obfuscation was not a barrier.** Both agents successfully traced data flow across file boundaries (SQL injection source→sink in different files, second-order XSS across profile→admin routes). This is a positive signal for real-world deployment.

**The most valuable next steps are:**

1. **Run adversarial tracks (4–6)** — confidence anchoring, explicit denial, and misdirection prompts — to test whether recall degrades when agents are told "the code is clean" or directed toward safe code.
2. **Add C/systems CWEs to the scorer alias table** — CWE-121 (buffer overflow) should be accepted as an equivalent for CWE-676 (gets()) since it is the correct consequence class.
3. **Run Tracks 2 and 3** for both agents to measure implicit detection (Track 2: code review without security mandate) and feature-implementation hygiene (Track 3: does the agent introduce new vulns?).
4. **Larger codebases** — the current projects are 50–200 lines. A 2,000+ line app would test whether strong recall holds when agents must navigate and prioritise.
