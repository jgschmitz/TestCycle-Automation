# Test Cycle AI Automation

## 📌 Project Overview

**Application Name:**\
Test Cycle AI Automation

**Business Unit:**\
Optum Insights -- Provider Tech Services

**Deployment:**\
100% On-Prem\
(Required due to hospital/provider security constraints -- no cloud LLMs
allowed)

------------------------------------------------------------------------

## 🧠 AI Stack

-   **LLM:** Meta LLaMA 7B / 13B (On-Prem)
-   **Automation:** Playwright + Python
-   **UI Navigation:** Browser-use
-   **AI Pattern:** Agent-based system with self-healing

------------------------------------------------------------------------

## 🎯 Business Problem

Currently:

-   600--700 test cases per release
-   1,700 manual hours per quarter
-   High defect leakage to production
-   Frequent vendor changes (ServiceNow monthly updates, Epic updates)
-   Scaling to 8 hospital clients (MPPs)

Manual testing is:

-   Expensive\
-   Error-prone\
-   Not scalable\
-   Slowing release cycles\
-   Creating production defects in healthcare environments

------------------------------------------------------------------------

## 🚨 Cost of Inaction

If no action is taken:

-   Continue spending \~1,700 hours per quarter\
-   Leak defects into hospital production systems\
-   Risk operational disruptions\
-   Slower vendor release adoption\
-   Higher remediation cost in production\
-   Inability to scale to 8 MPPs\
-   Forced to buy expensive licensed tools (e.g., AccelQ)

This initiative supports 2026 cost-reduction mandates.

------------------------------------------------------------------------

## 🔥 Why Now?

-   Corporate cost-cutting initiative for 2026\
-   Scaling to 8 hospital partnerships\
-   Increasing vendor release cadence\
-   Manual testing model is no longer sustainable\
-   POC starting in March\
-   Decision deadline: End of February

------------------------------------------------------------------------

## 🧠 Future State Vision

-   AI scans code changes automatically\
-   Generates new test cases\
-   Executes via Playwright\
-   Detects UI changes\
-   Self-heals test scripts\
-   Engineers approve fixes\
-   Reusable framework across all hospitals

### Target Outcomes

-   Reduce 1,700 hours → 200 hours (\~88% reduction)
-   Client expectation: 60--70% minimum automation

------------------------------------------------------------------------

## 📊 Success Metrics

-   \% reduction in manual testing hours\
-   \% reduction in defect leakage\
-   Time-to-release improvement\
-   Cost savings per hospital\
-   \% automated test coverage\
-   Self-heal success rate

------------------------------------------------------------------------

## 🏗️ System Architecture

```mermaid
flowchart LR

AE["Automation Engineer / System Engineer
Prompts with failure data"] -->|Initiates| ORCH

subgraph TOG["Test Objects Generator"]
  BU["Browser Use
Scans UI and gathers context"]
  ORCH["Orchestration Service (Python)
Translates UI data
Manages Prompts
Coordinates integrated tools"]
  BU --> ORCH
end

ORCH -->|Sends context and calls LLM| LLM["LLaMA (On-Prem)
Secure on-prem AI engine"]

subgraph TOOLS["Integrated Tools"]
  PR["Playwright Code Repo
Runs AI-generated scripts"]
  TCM["Test Case Management Tool
System of record for test cases"]
end

LLM -->|Commits code| PR
LLM -->|Creates or updates test cases| TCM

ORCH --> SH["Self-Healing Module
Updates tests based on UI or code changes
Proposes fixes for failed tests"]

SH -->|Fix PR scripts| PR

MDB["MongoDB (On-Prem)
Operational Data and Vector Embeddings"]

ORCH <--> |Store and retrieve context (Vector Search / RAG)| MDB
LLM  <--> |Retrieve relevant context (Vector Search / RAG)| MDB
SH   <--> |Store outcomes and learnings| MDB
TCM  -->  |Sync test case records| MDB
```



------------------------------------------------------------------------

## 📌 MongoDB Role

### 1️⃣ Operational Data Storage

-   Test cases (JSON)
-   Test execution reports
-   UI metadata
-   Change history
-   Self-heal decisions
-   Code change context
-   Hospital-specific configurations
-   Multi-tenant separation (8 MPPs)

### 2️⃣ Vector Embeddings (On-Prem Public Preview)

-   Test case embeddings
-   UI structure embeddings
-   Code diff embeddings
-   Execution logs
-   Defect pattern embeddings

### Enables:

-   Semantic search
-   RAG-style context retrieval
-   Context-aware test generation
-   Intelligent self-healing
-   Long-term AI memory

------------------------------------------------------------------------

## 📈 Scale Expectations

Initial:

-   600--700 test cases per client\
-   8 clients ≈ 5,000--6,000 test cases

Growth:

-   New test cases each release\
-   Expanding execution logs\
-   Growing embedding volume

Workload Pattern:

-   Write-heavy during releases\
-   Read-heavy during execution\
-   Vector similarity queries during AI generation
```

------------------------------------------------------------------------

## ❓ Open Questions

-   Expected data size at Day 1?
-   Retention policy?
-   Requests per day during release?
-   SLA requirements?
-   MVP vs full production timeline?
-   HA/DR expectations?
-   On-prem infrastructure footprint?

------------------------------------------------------------------------

## 🟢 Strategic Positioning

MongoDB is positioned as:

> The secure, on-prem AI memory layer enabling reusable, scalable,
> self-healing automation across hospital environments.

Not just a database.\
Not just a vector store.

But an AI operational memory platform.
