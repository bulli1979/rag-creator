# Batch Excel export — field reference

This document describes every sheet, column, and chart produced by `batch_chat.py` when you run a batch evaluation. Workbook text is **English**. Column names match the first row of the **Results** sheet exactly (plain language, spaces, scale hints like “0–1” in the header).

On **Results** and **Chunks**, row **1** uses **bold** and **wrap text**; column widths are set so long headers stay readable without horizontal scrolling as much as possible.

---

## Workbook structure (sheet order)

| Order | Sheet name   | Purpose |
|------:|--------------|---------|
| 1 | **Meta** | Run metadata, API URL, environment, configuration path, short scoring legend. |
| 2 | **Rubric** | Human scoring guide (RAG triad + Dim4): criteria and 0 / 1 / 2 anchor descriptions. |
| 3 | **Results** | One row per question: pipeline outputs, optional auto scores, manual score columns. |
| 4 | **Chunks** | One row per retrieved chunk (normalized view for filtering/pivoting). |
| 5 | **Eval_Charts** | *(Only if `evaluateAnswers` is true and at least one numeric auto score exists.)* Summary table(s) and bar charts for mean auto metrics. |

---

## Sheet: **Meta**

| Row | Column A (label) | Column B (value) | Description |
|-----|------------------|------------------|-------------|
| 1 | Created (UTC) | ISO-8601 timestamp | When the workbook was generated (UTC). |
| 2 | API | Base URL | `apiBaseUrl` used for `/api/chat` (no trailing slash in stored value). |
| 3 | Configuration | Absolute path | Path to the JSON config file used for this run. |
| 4 | Test environment (ID) | UUID or empty | Active `activePostgresEnvironmentId` after any `PUT /api/settings` from the batch run. |
| 5 | Test environment (name) | Display name or "—" | Human-readable name for that environment from `GET /api/settings`. |
| 6 | Questions (count) | Integer | Number of questions processed. |
| 7 | Scoring | Long text | Explains “Judge:” columns (0–1), “Human score:” columns (0–2), total column, and points to **Rubric** and **Eval_Charts**. |
| 8 | Chat settings (applied) | JSON | Present only if `applyChatSettings` was used: snapshot of overlay applied to `/api/chat/settings`. |

---

## Sheet: **Rubric**

Single reference table for **manual** scoring on **Results** (not formulas—human entry).

| Column | Meaning |
|--------|---------|
| A | Criterion name (e.g. Context relevance, Groundedness, …). |
| B | Short description of what to assess. |
| C–E | Anchors for **0**, **1**, and **2** points. |

**Dim4** depends on question **Type** on **Results**:

- **Objective** → use **Dim4: Accuracy** row (factual accuracy vs. `answerField` when you use it as reference).
- **Subjective** → use **Dim4: Completeness** row (coverage of the question).

**Scale:** all four manual dimensions use **0–2**. **Maximum** total manual score per question = **8** (sum of the four score cells on **Results**; see column **Human score: total (0–8)**).

---

## Sheet: **Results** — column reference

Row **1** = headers. Row **2+** = one question per row. Data validation (where applied): manual score columns allow only **0**, **1**, **2**, or blank.

**Display layout:** **Columns G and P are swapped** for the sheet only: **G** = **Judge: answer relevance (0–1)** (number format **0.000000**), **P** = **HTTP or request error**. Judge scores in **Q–S** also use **0.000000**. Charts and in-memory aggregation still follow the original field order.

### **Results** — physical column order (A → …)

| Col | Letter | Header | Description |
|-----|--------|--------|-------------|
| 1 | A | Row no. | 1-based index in batch order. |
| 2 | B | Question ID | From YAML or `inline-n`. |
| 3 | C | Question type | `Objective` / `Subjective` (or empty for legacy). |
| 4 | D | Question text | Message sent to `POST /api/chat`. |
| 5 | E | Ground truth (answerField) | Reference for judge when set. |
| 6 | F | Model answer | API answer text. |
| 7 | **G** | **Judge: answer relevance (0–1)** | Six decimals; judge only if `evaluateAnswers`. |
| 8 | H | Latency (ms) | `metrics.elapsedMs`. |
| 9 | I | Prompt tokens | |
| 10 | J | Completion tokens | |
| 11 | K | Total tokens | |
| 12 | L | Tokens per second | |
| 13 | M | Number of context chunks | |
| 14 | N | Retrieved chunks (summary) | One-line chunk list. |
| 15 | O | Retrieved chunks (full text for judge) | Long context text. |
| 16 | **P** | **HTTP or request error** | Swapped here from default logical order. |
| 17 | Q | Judge: context relevance (0–1) | Six decimals. |
| 18 | R | Judge: groundedness (0–1) | Six decimals. |
| 19 | S | Judge: answer correctness (0–1) | Six decimals; Objective + ground truth only. |
| 20 | T | Judge notes | |
| 21 | U | Judge error | |
| 22 | V | Human score: context relevance (0–2) | Manual (see **Rubric**). |
| 23 | W | Human score: groundedness (0–2) | |
| 24 | X | Human score: answer relevance (0–2) | |
| 25 | Y | Human score: Dim4 criterion (hint) | Accuracy / Completeness hint. |
| 26 | Z | Human score: Dim4 (0–2) | |
| 27 | AA | Human score: total (0–8) | Formula: sum of V, W, X, Z. |

---

## Sheet: **Chunks**

One row per chunk per question. Useful for auditing retrieval without parsing **Retrieved chunks (full text for judge)** on **Results**.

| Column | Description |
|--------|-------------|
| **Question row no.** | Matches **Results → Row no.** |
| **Chunk position** | 1-based position in the chunk list for that answer. |
| **File name** | Source file name from the API chunk object. |
| **Chunk index** | Chunk index in that file. |
| **Document ID** | Document identifier when provided. |
| **Similarity** | Retrieval similarity score when provided. |
| **Source** | Source path / URI field from API. |
| **Text excerpt** | Truncated chunk text for spreadsheet size limits. |

---

## Sheet: **Eval_Charts** *(conditional)*

Created when the judge ran and **at least one** of the four numeric auto metrics exists. Aggregations are computed from the same in-memory rows written to **Results** (consistent with the console summary at the end of a run).

### Table 1 — overall means (rows 1–5)

| Cell | Content |
|------|---------|
| A1 | Header: `Metric (auto, 0–1)` |
| B1 | Header: `Mean` |
| A2–A5 | Metric labels: Answer relevance, Context relevance, Groundedness, Answer correctness |
| B2–B5 | **Mean** of that column over all rows that have a numeric value in **Results**. |

**Important:** For **Answer correctness**, only **Objective** rows with a non-empty **answerField** receive a value in **Results**; therefore the mean and the bar chart for that metric are **restricted to that subset**, not to all questions.

### Chart 1 — “Mean LLM scores (0–1)”

- **Type:** Column bar chart.  
- **Categories:** The four metric names (column A, rows 2–5).  
- **Values:** Column B means (row 1 used as series title “Mean”).  
- **Placement:** Anchored near cell **D2**.  
- **Y-axis:** Mean (0–1 scale conceptually).  
- **X-axis:** Metric name.

If no numeric scores exist, a short message is written near **D2** instead of the chart.

### Accuracy summary (rows 7–8)

| Cell | Meaning |
|------|---------|
| **A7** | Label: accuracy line for Objective + answerField. |
| **B7** | Mean of **Judge: answer correctness (0–1)** over Objective rows with ground truth (same subset as the correctness bar). |
| **C7** | `n=` count of those rows. |
| **A8** | Note explaining that the correctness column and bar are limited to Objective + `answerField`. |

### Table 2 — means by question **Type** (from row 12)

| Row 12 | Header row: **Question type** (A12) + the same four metric names (B12–E12). |
| Rows 13+ | One row per distinct **Type** string seen in **Results** (e.g. `Objective`, `Subjective`, `?` for unknown). Cells B–E = **mean** of that metric **within that type**, only counting rows that have a numeric value for that metric. |

### Chart 2 — “Mean scores by question type (clustered)”

- **Type:** Clustered column chart.  
- **Categories:** Question type (column A from row 13 onward).  
- **Series:** Four metrics (columns B–E), same order as chart 1.  
- **Placement:** Anchored near **D18**.  
- **Interpretation:** Compares, e.g., average relevance for Subjective vs. Objective rows **separately**; correctness may be empty for types that never receive scores.

---

## Console output (same run)

After building the workbook, the script prints **“Auto evaluation (LLM judge)”**: mean of each auto metric (with **n**), plus **Accuracy** as the mean of correctness values for **Objective + answerField** only. If `evaluateAnswers` is false, it states that auto metrics were not computed.

---

## Configuration pointers

| JSON key | Effect on Excel |
|----------|-----------------|
| `evaluateAnswers` | Enables judge columns and **Eval_Charts** (when any score exists). |
| `evalJudge.*` | Judge URL, model, timeouts, context truncation (`maxContextChars`), retries. |
| `outputExcel` | Output `.xlsx` path. |

---

## Truncation

Very long cells (**Model answer**, **Retrieved chunks (summary)**, **Retrieved chunks (full text for judge)**, chunk **Text excerpt**, **Judge error**) may be truncated with the suffix  
`… [truncated due to Excel cell size limit]`  
because Excel has a per-cell character limit (~32k).
