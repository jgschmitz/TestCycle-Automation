# Quick Start: MongoDB + LLaMA Test Automation

## 🚀 Setup (On-Prem Environment)

### 1. Install MongoDB Enterprise (On-Prem)

```bash
# Download MongoDB Enterprise (supports Vector Search)
wget https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-enterprise-ubuntu2204-7.0.5.tgz
tar -zxvf mongodb-linux-x86_64-enterprise-ubuntu2204-7.0.5.tgz
sudo mv mongodb-linux-x86_64-enterprise-ubuntu2204-7.0.5 /opt/mongodb

# Create data directory
sudo mkdir -p /data/db
sudo chown -R $USER:$USER /data/db

# Start MongoDB
/opt/mongodb/bin/mongod --dbpath /data/db --port 27017 --bind_ip 0.0.0.0
```

### 2. Install llama.cpp

```bash
# Clone llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Build with CPU support (or CUDA for GPU)
make

# Download LLaMA 7B model (quantized for efficiency)
# Get from HuggingFace: https://huggingface.co/TheBloke/Llama-2-7B-GGUF
wget https://huggingface.co/TheBloke/Llama-2-7B-GGUF/resolve/main/llama-2-7b.Q4_K_M.gguf \
  -O models/llama-7b-q4.gguf

# Start llama.cpp server
./server -m models/llama-7b-q4.gguf --port 8080 --ctx-size 4096 --threads 8
```

### 3. Install Python Dependencies

```bash
cd TestCycle-Automation
pip install -r requirements.txt

# Download sentence-transformers model (runs on CPU, ~100MB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### 4. Setup MongoDB Vector Search Index

```javascript
// Connect to MongoDB
mongosh

// Create vector search index for test case embeddings
use test_automation_client_A

db.vector_embeddings.createSearchIndex({
  name: "test_case_embeddings",
  type: "vectorSearch",
  definition: {
    fields: [{
      type: "vector",
      path: "embedding",
      numDimensions: 384,  // all-MiniLM-L6-v2 dimension
      similarity: "cosine"
    }]
  }
})
```

---

## 📝 Usage Examples

### Example 1: Basic State Management

```python
from src.mongodb_manager import MongoDBManager, TestCase
from datetime import datetime

# Initialize
mongo = MongoDBManager()
hospital = "client_A"
mongo.initialize_collections(hospital)

# Create test case
test = TestCase(
    test_id="TC_LOGIN_001",
    name="Epic Patient Portal Login",
    hospital=hospital,
    description="Validates Epic login flow",
    playwright_script="""
from playwright.sync_api import Page

def test_login(page: Page):
    page.goto('https://epic.example.com/login')
    page.fill('#username', 'testuser')
    page.fill('#password', 'testpass')
    page.click('#login-btn')
    assert page.is_visible('.dashboard')
""",
    tags=["epic", "authentication"]
)

mongo.save_test_case(test)
print(f"Saved test: {test.test_id}")
```

### Example 2: Vector Search RAG

```python
from src.vector_rag import VectorRAG
from src.mongodb_manager import MongoDBManager

mongo = MongoDBManager()
rag = VectorRAG(mongo)

hospital = "client_A"

# Index a test case
test_content = """
Test: Patient Registration
Description: Register new patient with demographics
Steps:
1. Navigate to /patient/registration
2. Fill #first-name, #last-name, #dob
3. Click #submit-btn
4. Verify success message
"""

rag.index_test_case(
    hospital=hospital,
    test_case_id="TC_REG_001",
    test_content=test_content
)

# Later: Find similar tests to avoid duplication
query = "create test for registering patient information"
similar = rag.retrieve_similar_tests(hospital, query, limit=3)

print("Similar existing tests:")
for ctx in similar:
    print(f"- {ctx.test_case_id} (score: {ctx.similarity_score:.3f})")
    print(f"  {ctx.content[:200]}...\n")
```

### Example 3: AI Test Generation with LLaMA

```python
from src.llama_integration import LLaMAClient, AITestGenerator
from src.vector_rag import VectorRAG
from src.mongodb_manager import MongoDBManager

# Initialize (llama.cpp server must be running)
mongo = MongoDBManager()
llama = LLaMAClient(base_url="http://localhost:8080")
rag = VectorRAG(mongo)
ai_gen = AITestGenerator(llama, mongo, rag)

hospital = "client_A"

# Current UI from browser-use
ui_snapshot = {
    "url": "https://epic.hospital.com/billing",
    "elements": [
        {"selector": "#patient-id", "type": "input"},
        {"selector": "#service-date", "type": "date"},
        {"selector": "#submit-claim", "type": "button", "text": "Submit"}
    ]
}

# Generate test case with RAG context
test_case = ai_gen.generate_test_case(
    hospital=hospital,
    test_description="Test billing claim submission for patient visit",
    ui_snapshot=ui_snapshot,
    vendor_context={"epic_version": "2025.11"}
)

print(f"Generated Test ID: {test_case.test_id}")
print(f"Script:\n{test_case.playwright_script}")
```

### Example 4: Self-Healing

```python
from src.llama_integration import AITestGenerator
from src.mongodb_manager import MongoDBManager, TestExecution
from src.vector_rag import VectorRAG
from src.llama_integration import LLaMAClient
from datetime import datetime

mongo = MongoDBManager()
llama = LLaMAClient()
rag = VectorRAG(mongo)
ai_gen = AITestGenerator(llama, mongo, rag)

hospital = "client_A"

# Test failed
execution = TestExecution(
    execution_id="exec_001",
    test_case_id="TC_LOGIN_001",
    hospital=hospital,
    status="failed",
    duration_ms=3200,
    timestamp=datetime.utcnow(),
    error_message="Element not found: #login-btn"
)
mongo.save_execution(execution)

# Updated UI (button ID changed)
new_ui = {
    "url": "https://epic.hospital.com/login",
    "elements": [
        {"selector": "#username", "type": "input"},
        {"selector": "#password", "type": "input"},
        {"selector": "#login-button-v2", "type": "button"}  # Changed!
    ]
}

# AI generates fix
heal = ai_gen.generate_self_heal_fix(
    hospital=hospital,
    test_id="TC_LOGIN_001",
    failure_reason="Element not found: #login-btn",
    current_ui_snapshot=new_ui
)

print(f"Self-Heal ID: {heal.heal_id}")
print(f"Detected Change: {heal.ui_change_detected}")
print(f"Proposed Fix: {heal.fix_applied}")
print(f"Confidence: {heal.confidence_score:.0%}")
print(f"Engineer Approval Required: {not heal.engineer_approved}")
```

### Example 5: Analytics & KPIs

```python
from src.mongodb_manager import MongoDBManager

mongo = MongoDBManager()
hospital = "client_A"

# Get flaky tests
flaky = mongo.get_flaky_tests(hospital, min_executions=10)
print(f"\n🔴 Flaky Tests ({len(flaky)}):")
for test in flaky:
    print(f"  {test['test_case_id']}: {test['pass_rate']:.0%} pass rate")

# Get self-heal success rate (key KPI)
heal_stats = mongo.get_heal_success_rate(hospital, days=30)
print(f"\n🤖 Self-Heal Stats (30 days):")
print(f"  Total Heals: {heal_stats['total_heals']}")
print(f"  Approved: {heal_stats['approved_heals']}")
print(f"  Approval Rate: {heal_stats['approval_rate']:.0%}")
print(f"  Avg Confidence: {heal_stats['avg_confidence']:.0%}")

# Get execution stats
stats = mongo.get_execution_stats(hospital, days=7)
print(f"\n📊 Execution Stats (7 days):")
for status, data in stats.items():
    if status != "pass_rate":
        print(f"  {status}: {data['count']} tests, avg {data['avg_duration_ms']:.0f}ms")
print(f"  Overall Pass Rate: {stats.get('pass_rate', 0):.0%}")
```

---

## 🏥 Multi-Tenant Setup (8 Hospitals)

```python
from src.mongodb_manager import MongoDBManager

mongo = MongoDBManager()

# Initialize databases for all 8 hospitals
hospitals = ["client_A", "client_B", "client_C", "client_D", 
             "client_E", "client_F", "client_G", "client_H"]

for hospital in hospitals:
    mongo.initialize_collections(hospital)
    print(f"✅ Initialized database: test_automation_{hospital}")

# Each hospital has isolated data
# Database names:
# - test_automation_client_A
# - test_automation_client_B
# - test_automation_client_C
# ... etc
```

---

## 🔍 Why MongoDB is Critical

### 1. **State Persistence** (vs flat files)

**Without MongoDB:**
```python
# Fragile, no concurrency, no querying
import json
with open(f"tests_{hospital}.json", "w") as f:
    json.dump(tests, f)  # Overwrites everything!
```

**With MongoDB:**
```python
# Concurrent-safe, queryable, versioned
mongo.save_test_case(test_case)  # Atomic operation
flaky = mongo.get_flaky_tests(hospital)  # Complex analytics
```

### 2. **Vector Search** (hallucination reduction)

**Without Vector Search:**
- LLaMA generates tests for UI elements that don't exist
- Duplicates existing test cases
- Misses recent vendor updates

**With MongoDB Vector Search:**
```python
# Retrieve 5 most similar past tests
similar = rag.retrieve_similar_tests(hospital, "patient login test", limit=5)

# Build grounded prompt
augmented_prompt = rag.build_rag_prompt(hospital, task_description)
# LLaMA now has real context → fewer hallucinations
```

### 3. **Multi-Hospital Scale**

**8 Hospitals = 5,000+ test cases**

MongoDB enables:
- Database-per-tenant isolation (compliance)
- Efficient vector similarity search across thousands of embeddings
- Complex analytics (flaky test detection, heal success rate)
- Horizontal scaling via sharding (future growth)

---

## 📈 Expected Results

### Baseline (No MongoDB)
- Manual test investigation: **30-60 min per failure**
- Duplicate test creation: **~15% of tests**
- LLM hallucination rate: **~40%** (non-existent selectors)

### With MongoDB + Vector RAG
- Automated self-heal suggestion: **2-5 min**
- Duplicate test creation: **<5%** (vector similarity detection)
- LLM hallucination rate: **<10%** (grounded in real UI data)

### ROI Calculation
- **Manual testing hours saved**: 1,700 → 200 hours/quarter (**88% reduction**)
- **Cost savings**: ~$850K over 3 years (8 hospitals)
- **Self-heal approval rate**: Target **>80%** (with good training data)

---

## 🛠️ Troubleshooting

### MongoDB Connection Issues
```bash
# Check MongoDB is running
ps aux | grep mongod

# Test connection
mongosh --eval "db.adminCommand('ping')"
```

### llama.cpp Server Issues
```bash
# Check server is running
curl http://localhost:8080/health

# View server logs
# (check terminal where ./server was started)
```

### Vector Search Not Working
```javascript
// Verify index exists
use test_automation_client_A
db.vector_embeddings.getSearchIndexes()

// Rebuild if needed
db.vector_embeddings.dropSearchIndex("test_case_embeddings")
// Then recreate (see Setup step 4)
```

---

## 📚 Next Steps

1. **POC (March 2026)**
   - Deploy MongoDB + llama.cpp on single on-prem server
   - Test with 100 test cases from Client A
   - Measure self-heal success rate

2. **Production Rollout (Q2 2026)**
   - Scale to all 8 hospitals
   - Enable MongoDB replica set (3 nodes) for HA
   - Implement automated backup/restore

3. **Optimization**
   - Fine-tune LLaMA on approved self-healing fixes
   - Expand vector search to code diffs, execution logs
   - Build engineer approval dashboard
