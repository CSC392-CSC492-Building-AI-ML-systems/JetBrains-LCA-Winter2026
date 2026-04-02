# 🤖 AI Software Engineering & Security Benchmarks

Welcome to the central repository for evaluating Large Language Models (LLMs) and AI coding agents on real-world software engineering tasks. 

This repository contains a suite of distinct benchmarks, each targeting a specific phase of the software development and auditing lifecycle: from pinpointing where a bug lives, to writing the code to fix it, to auditing the codebase for security vulnerabilities.

## 📂 Repository Structure & Benchmarks

This repository is divided into three main benchmarking environments. Please navigate to their respective directories for detailed setup, execution instructions, and dedicated documentation.

### 1. [`/SWE-bench`](./SWE-bench/) — Issue Resolution & Patch Generation
SWE-bench evaluates whether language models can resolve real-world software issues collected from GitHub. Given a codebase and an issue, the agent must generate a patch that fixes the problem.
* **Key Features:** Docker-based reproducible evaluation harness, multiple dataset variants (Lite, Verified, Multimodal), and cloud-based evaluation support (Modal, sb-cli).
* **Docs:** [SWE-bench Documentation](https://swebench.com/SWE-bench/)

### 2. [`/bug_localization`](./bug_localization/) — File-Level Bug Localization
Part of the Long Code Arena, this benchmark isolates the problem of *finding* the bug. Given an issue description and the repository state, the model must identify the exact files within the project that need to be modified.
* **Key Features:** Embedding-based baselines (TF-IDF, GTE, BM25) and Chat-based LLM baselines (OpenAI, Gemini, Claude) with automated metrics (Precision, Recall, F1).

### 3. [`/SWE-bench/swebench/security`](.SWE-bench/swebench/security/) — VulnAgentBench
A security vulnerability detection benchmark built on top of the SWE-bench agent harness. It evaluates whether coding agents can detect pre-planted vulnerabilities (like SQLi, XSS, IDOR) in realistic web applications.
* **Key Features:** Evaluates agents across 3 tracks (Explicit Detection, Implicit Detection, and Feature Implementation) to see if they can find vulnerabilities even when not explicitly prompted to look for them. Includes robust fuzzy-matching and Semgrep integration.

---

## 🚀 Getting Started

Because each benchmark evaluates a different capability and uses different underlying datasets, **there is no global execution script.** To get started, please navigate to the specific benchmark directory you are interested in and follow the `README.md` located inside that folder:

* **For SWE-bench:** `cd SWE-bench && pip install -e .` (Requires Docker)
* **For Bug Localization:** `cd bug_localization && pip install -r requirements.txt`
* **For VulnAgentBench:** `cd SWE-bench/swebench/security` (Requires Docker and the SWE-bench base installation)

## 🛠️ Global Prerequisites

While each sub-project has its own dependencies, interacting with this repository generally requires:
* **Python 3.8+**
* **Docker** (Crucial for safely executing SWE-bench and VulnAgentBench evaluations in isolated containers).
* **API Keys** for the LLMs you wish to evaluate (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`).

## ✍️ License
This repository is licensed under the MIT License. Please see the individual directories for specific citations and research paper references related to each benchmark.