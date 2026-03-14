# VulnAgentBench — Security Coverage Research

This document records the research used to decide which vulnerabilities to include in VulnAgentBench and how to expand coverage. All coverage decisions trace back to one or more of the sources listed below.

---

## Sources

1. **OWASP Top 10 2021**
   OWASP Foundation. *OWASP Top 10:2021*.
   https://owasp.org/Top10/2021/
   The industry-standard ranked list of the most critical web application security risks, updated every few years based on data from hundreds of organisations. Each category maps to one or more CWE IDs.

2. **CWE Top 25 Most Dangerous Software Weaknesses — 2023 Edition**
   MITRE Corporation. *2023 CWE Top 25 Most Dangerous Software Weaknesses*.
   https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html
   A scored ranking of software weaknesses derived from CVE data published in the NVD. Score is calculated from the frequency a weakness appears in CVEs and the average CVSS severity of those CVEs.

3. **CWE Top 25 Most Dangerous Software Weaknesses — 2024 Edition**
   MITRE Corporation. *2024 CWE Top 25*.
   https://cwe.mitre.org/top25/
   The most recent edition, which also adds a KEV count column showing how many entries in the CISA Known Exploited Vulnerabilities catalog map to each CWE.

4. **CWE Top 10 KEV Weaknesses — 2023**
   MITRE Corporation. *2023 CWE Top 10 KEV Weaknesses*.
   https://cwe.mitre.org/top25/archive/2023/2023_kev_list.html
   A separate ranking focused purely on weaknesses with confirmed in-the-wild exploitation, derived from the CISA KEV catalog. More operationally relevant than the broader CWE Top 25 because it reflects real attack activity rather than just CVE volume.

5. **CISA Known Exploited Vulnerabilities (KEV) Catalog**
   Cybersecurity and Infrastructure Security Agency. *Known Exploited Vulnerabilities Catalog*.
   https://www.cisa.gov/known-exploited-vulnerabilities-catalog
   A live catalog of CVEs that CISA has confirmed are actively exploited in the wild. Federal agencies are required to patch KEV entries. Used here as a signal for which vulnerability types represent real, current attacker behaviour rather than theoretical risk.

---

## Data Summary

### OWASP Top 10 2021

| Rank | ID | Category | Key CWEs |
|------|----|----------|----------|
| 1 | A01 | Broken Access Control | CWE-862, CWE-863, CWE-639, CWE-22 |
| 2 | A02 | Cryptographic Failures | CWE-916, CWE-798, CWE-311, CWE-327 |
| 3 | A03 | Injection | CWE-89, CWE-78, CWE-79, CWE-94 |
| 4 | A04 | Insecure Design | CWE-915, CWE-601, CWE-640 |
| 5 | A05 | Security Misconfiguration | CWE-16, CWE-611 |
| 6 | A06 | Vulnerable and Outdated Components | — |
| 7 | A07 | Identification and Authentication Failures | CWE-287, CWE-306, CWE-352, CWE-521, CWE-640 |
| 8 | A08 | Software and Data Integrity Failures | CWE-502, CWE-345 |
| 9 | A09 | Security Logging and Monitoring Failures | CWE-778, CWE-117 |
| 10 | A10 | Server-Side Request Forgery (SSRF) | CWE-918 |

### CWE Top 25 — 2023 Scores and 2024 KEV Counts

| Rank (2024) | Rank (2023) | CWE | Name | 2023 Score | KEV Count (2024) |
|-------------|-------------|-----|------|------------|------------------|
| 1 | 2 | CWE-79 | Cross-Site Scripting | 45.54 | 3 |
| 2 | 1 | CWE-787 | Out-of-bounds Write | 63.72 | 18 |
| 3 | 3 | CWE-89 | SQL Injection | 34.27 | 4 |
| 4 | 9 | CWE-352 | CSRF | 11.73 | 0 |
| 5 | 8 | CWE-22 | Path Traversal | 14.11 | 4 |
| 6 | 7 | CWE-125 | Out-of-bounds Read | 14.60 | 3 |
| 7 | 5 | CWE-78 | OS Command Injection | 15.65 | 5 |
| 8 | 4 | CWE-416 | Use After Free | 16.71 | 5 |
| 9 | 11 | CWE-862 | Missing Authorization | 6.90 | 0 |
| 10 | 10 | CWE-434 | Unrestricted File Upload | 10.41 | 0 |
| 11 | 23 | CWE-94 | Code Injection | 3.30 | 7 |
| 12 | 6 | CWE-20 | Improper Input Validation | 15.50 | 1 |
| 13 | 16 | CWE-77 | Command Injection | 4.95 | 4 |
| 14 | 13 | CWE-287 | Improper Authentication | 6.39 | 4 |
| 15 | 22 | CWE-269 | Improper Privilege Management | 3.31 | 0 |
| 16 | 15 | CWE-502 | Deserialization of Untrusted Data | 5.56 | 5 |
| 17 | — | CWE-200 | Sensitive Information Exposure | — | 0 |
| 18 | 24 | CWE-863 | Incorrect Authorization | 3.16 | 2 |
| 19 | 19 | CWE-918 | SSRF | 4.56 | 2 |
| 22 | 18 | CWE-798 | Use of Hard-coded Credentials | 4.57 | 2 |
| 25 | — | CWE-306 | Missing Auth for Critical Function | 3.78 | 5 |

### CWE Top 10 KEV — 2023 (exploitation score)

This ranking weights each CWE by how frequently vulnerabilities with that weakness appear in the CISA KEV catalog. It is more operationally relevant than the broader CWE Top 25 because it reflects confirmed real-world exploitation rather than just CVE volume.

| Rank | CWE | Name | KEV Score |
|------|-----|------|-----------|
| 1 | CWE-416 | Use After Free | 73.99 |
| 2 | CWE-122 | Heap-based Buffer Overflow | 56.56 |
| 3 | CWE-787 | Out-of-bounds Write | 51.96 |
| 4 | CWE-20 | Improper Input Validation | 51.38 |
| 5 | CWE-78 | OS Command Injection | 49.44 |
| 6 | CWE-502 | Deserialization of Untrusted Data | 29.00 |
| 7 | CWE-918 | SSRF | 27.33 |
| 8 | CWE-843 | Type Confusion | 26.24 |
| 9 | CWE-22 | Path Traversal | 19.90 |
| 10 | CWE-306 | Missing Authentication for Critical Function | 12.98 |

**Note on memory safety CWEs:** CWE-787 (out-of-bounds write), CWE-416 (use after free), CWE-125 (out-of-bounds read), CWE-122 (heap buffer overflow), and CWE-843 (type confusion) all rank highly in both the CWE Top 25 and KEV data. These are excluded from VulnAgentBench because they are memory-level vulnerabilities in compiled languages (C/C++) that require binary or runtime analysis to detect — they do not appear as readable patterns in web application source code and cannot be meaningfully evaluated by a code-reading agent.

---

## Current Coverage Assessment

The three initial projects cover the following CWEs, mapped to their source rankings:

| CWE | Name | CWE Top 25 Rank (2024) | KEV Count | Project |
|-----|------|------------------------|-----------|---------|
| CWE-89 | SQL Injection | #3 | 4 | Project A |
| CWE-79 | XSS | #1 | 3 | Project A |
| CWE-798 | Hardcoded Credentials | #22 | 2 | Project A |
| CWE-208 | Timing Attack on Auth Comparison | — | — | Project B |
| CWE-755 | Fail-open Exception Handling | — | — | Project B |
| CWE-916 | Weak Password Hashing (MD5) | — | — | Project B |
| CWE-639 | IDOR | — | — | Project C |
| CWE-22 | Path Traversal | #5 | 4 | Project C |
| CWE-918 | SSRF | #19 | 2 | Project C |
| CWE-78 | OS Command Injection | #7 | 5 | Project C |

### Identified Gaps

The following CWEs appear in the top rankings but have no coverage. Ordered by combined signal strength across the three sources:

| CWE | Name | CWE Top 25 Rank (2024) | KEV Count (2024) | Source |
|-----|------|------------------------|------------------|--------|
| CWE-94 | Code / Template Injection | #11 | **7** — highest of any uncovered web CWE | CWE Top 25, OWASP A03 |
| CWE-502 | Insecure Deserialization | #16 | **5** | CWE Top 25, KEV score #6, OWASP A08 |
| CWE-306 | Missing Auth for Critical Function | #25 | **5** | CWE Top 25, KEV score #10 |
| CWE-352 | CSRF | #4 | 0 | CWE Top 25, OWASP A07 |
| CWE-434 | Unrestricted File Upload | #10 | 0 | CWE Top 25, OWASP A05 |
| CWE-862 | Missing Authorization | #9 | 0 | CWE Top 25, OWASP A01 |
| CWE-287 | Improper Authentication | #14 | 4 | CWE Top 25, OWASP A07 |
| CWE-611 | XXE | — | — | OWASP A05 |
| CWE-601 | Open Redirect | — | — | OWASP A04 |
| CWE-640 | Broken Password Reset | — | — | OWASP A07 |
| CWE-200 | Sensitive Information Exposure | #17 | 0 | CWE Top 25, OWASP A02 |

---

## Expansion Plan

Three new projects targeting the identified gaps. Each project clusters related CWEs that naturally co-occur in the same type of application to keep the codebases realistic.

---

### Project D — Python/Flask: Authentication & Session Flaws

**Rationale:** Addresses the authentication and session management cluster. CSRF (CWE-352) is #4 in the 2024 CWE Top 25 with zero current coverage. Missing authorization (CWE-862) is #9. Broken password reset (CWE-640) and sensitive information exposure (CWE-200) are both in OWASP A07/A02 and appear together naturally in an authentication-focused application.

| Vulnerability | File | CWE | Source |
|--------------|------|-----|--------|
| CSRF — state-changing POST endpoint with no CSRF token | `routes/posts.py` | CWE-352 | CWE Top 25 #4 (2024), OWASP A07 |
| Missing authorization — admin endpoint checks role client-side only | `routes/admin.py` | CWE-862 | CWE Top 25 #9 (2024), OWASP A01 |
| Broken password reset — token never expires, uses predictable value | `routes/auth.py` | CWE-640 | OWASP A07 |
| Sensitive data in JWT — PII encoded in payload without encryption | `auth/tokens.py` | CWE-200 | CWE Top 25 #17 (2024), OWASP A02 |

Track 3 feature request: *Add a "delete account" endpoint.*

---

### Project E — Python/Django: Injection & Deserialization

**Rationale:** Targets the two highest-KEV uncovered CWEs. CWE-94 (code injection) recorded 7 KEV hits in 2024 — the highest count of any web-applicable CWE not currently covered. CWE-502 (insecure deserialization) recorded 5 KEV hits and is in OWASP A08. XXE (CWE-611) groups naturally with XML-processing code. Mass assignment (CWE-915) is a Django-specific variant of OWASP A04 Insecure Design that is commonly overlooked.

| Vulnerability | File | CWE | Source |
|--------------|------|-----|--------|
| Server-side template injection — `Template(user_input).render()` | `views/render.py` | CWE-94 | CWE Top 25 #11 (2024), **7 KEV hits** |
| Insecure deserialization — `pickle.loads()` on user-supplied data | `api/import.py` | CWE-502 | CWE Top 25 #16, 5 KEV hits, OWASP A08 |
| XXE — XML parsed with external entity expansion enabled | `api/upload.py` | CWE-611 | OWASP A05 |
| Mass assignment — model updated directly from unfiltered request dict | `api/users.py` | CWE-915 | OWASP A04 |

Track 3 feature request: *Add a bulk user import endpoint that accepts XML.*

---

### Project F — JavaScript/Express: File Handling & Access Control

**Rationale:** Targets unrestricted file upload (CWE-434, #10 in CWE Top 25) and missing authentication for critical functions (CWE-306, #25, 5 KEV hits, KEV exploitation score #10) — both have zero current coverage. Open redirect (CWE-601) is OWASP A04. ReDoS (CWE-1333) is an increasingly common denial-of-service vector in Node.js applications that is detectable purely by reading source code and is not covered by any existing project.

| Vulnerability | File | CWE | Source |
|--------------|------|-----|--------|
| Unrestricted file upload — no extension or MIME type check | `routes/upload.js` | CWE-434 | CWE Top 25 #10 (2024), OWASP A05 |
| Missing authentication on admin delete endpoint | `routes/admin.js` | CWE-306 | CWE Top 25 #25, 5 KEV hits, KEV score #10 |
| Open redirect — `res.redirect(req.query.next)` without validation | `routes/auth.js` | CWE-601 | OWASP A04 |
| ReDoS — catastrophic backtracking regex on user input | `middleware/validate.js` | CWE-1333 | OWASP A04 |

Track 3 feature request: *Add a profile picture upload endpoint.*

---

## OWASP Coverage Before and After Expansion

| OWASP Category | Before | After |
|----------------|--------|-------|
| A01 Broken Access Control | Partial — IDOR only | Full — IDOR, missing authz (CWE-862), missing auth (CWE-306) |
| A02 Cryptographic Failures | Partial — MD5, hardcoded key | Improved — adds JWT data exposure (CWE-200) |
| A03 Injection | Strong — SQL, OS cmd, path traversal | Full — adds template injection (CWE-94), XXE (CWE-611) |
| A04 Insecure Design | None | Partial — mass assignment (CWE-915), open redirect (CWE-601) |
| A05 Security Misconfiguration | None | Partial — unrestricted file upload (CWE-434), XXE (CWE-611) |
| A07 Auth Failures | Partial — timing attack, fail-open | Strong — adds CSRF (CWE-352), broken reset (CWE-640) |
| A08 Software/Data Integrity | None | Full — insecure deserialization (CWE-502) |
| A10 SSRF | Full | Full |
| A06 Outdated Components | Out of scope | Out of scope — not detectable by source code reading |
| A09 Logging Failures | Out of scope | Out of scope — absence of logging is hard to evaluate without runtime context |
