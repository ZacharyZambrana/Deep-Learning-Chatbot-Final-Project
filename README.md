# Grassroots Furniture · Customer Concierge Chatbot

An enterprise-grade, agentic customer service chatbot for **Grassroots Furniture** (handcrafted, sustainable furniture). Built with **Retrieval-Augmented Generation (RAG)**, **local LLMs via Ollama**, **hybrid semantic & lexical search**, **relational database integration**, and strict **anti-hallucination guardrails**.

---

## Architecture Overview

The system combines unstructured knowledge base retrieval from help-center articles with live relational SQL transactional records, wrapped in multi-layered safety and privacy guardrails:

```text
                               +----------------------------------------+
                               |        User Input / Streamlit UI       |
                               +----------------------------------------+
                                                    |
                                                    v
                               +----------------------------------------+
                               |     Memory & Entity Extraction         |
                               |    - Extracts & stores Order IDs       |
                               |    - Tracks multi-turn dialogue state  |
                               +----------------------------------------+
                                                    |
                       +----------------------------+----------------------------+
                       |                                                         |
                       v                                                         v
    +--------------------------------------+                  +--------------------------------------+
    |    Transactional Database Lookup     |                  |       Hybrid Retrieval Engine        |
    |  - SQLite (`data/grassroots.db`)     |                  |  - BM25 Okapi (Lexical)              |
    |  - Read-Only connection              |                  |  - Fine-Tuned MiniLM (Dense Vectors) |
    |  - Scoped by signed-in Customer ID   |                  |  - Reciprocal Rank Fusion (RRF)      |
    |  - Enforces Multi-Tenant Isolation   |                  +--------------------------------------+
    +--------------------------------------+                                     |
                       |                                                         v
                       |                                      +--------------------------------------+
                       |                                      |      Cross-Encoder Re-Ranker         |
                       |                                      |   ms-marco-MiniLM-L-6-v2             |
                       |                                      +--------------------------------------+
                       |                                                         |
                       |                                                         v
                       |                                      +--------------------------------------+
                       |                                      |      Security & Audience Filter      |
                       |                                      |   - Drops restricted/internal docs   |
                       |                                      |   - Ask-first decline pre-check      |
                       |                                      +--------------------------------------+
                       |                                                         |
                       +----------------------------+----------------------------+
                                                    |
                                                    v
                               +----------------------------------------+
                               |        Prompt Augmentation Engine      |
                               |  - Injects verified KNOWN FACTS (SQL)  |
                               |  - Formats retrieved SOURCES ([KB-xxx])|
                               +----------------------------------------+
                                                    |
                                                    v
                               +----------------------------------------+
                               |          Local LLM Generation          |
                               |     Ollama (`llama3.2:3b` / 8B)        |
                               |  - Constrained strictly to context     |
                               |  - Mandates explicit citations [KB-xxx]|
                               +----------------------------------------+
                                                    |
                                                    v
                               +----------------------------------------+
                               |       Post-Generation Guardrails       |
                               |  - Unsupported claims & number checks  |
                               |  - Leaked internal document detector   |
                               |  - Safe decline fallback on failure    |
                               +----------------------------------------+
                                                    |
                                                    v
                               +----------------------------------------+
                               |         Verified Customer Reply        |
                               +----------------------------------------+
```

---

## Key Capabilities

1. **Grounded Policy Question Answering (RAG)**:
   * Articles are split into topical sections and indexed with dense embeddings (`sentence-transformers/all-MiniLM-L6-v2`) and keyword indices (`rank-bm25`).
   * Retrieval combines dense similarity and BM25 scores via Reciprocal Rank Fusion (RRF) followed by a Cross-Encoder re-ranking step.
   * Answers cite exact source article IDs (`[KB-001]`, `[KB-006]`, etc.).

2. **Live Order Integration & Contextual Memory**:
   * Recognizes order numbers (e.g., `GF-40318`) and queries `grassroots.db` in read-only mode.
   * Multi-turn state memory (`remember`) persists order facts across turns so customers can ask follow-up questions without re-typing their order numbers.

3. **Multi-Tenant Privacy & Data Isolation**:
   * Queries are strictly scoped to the active signed-in customer ID (`SELECT * FROM orders WHERE order_id = ? AND customer_id = ?`).
   * Customers cannot access or view orders belonging to other accounts.

4. **Deep Learning Fine-Tuning**:
   * Synthetic training query pairs generated from public help-center passages using the local 8B model (`llama3.1:8b`).
   * MiniLM embedding model fine-tuned in PyTorch using in-batch negatives loss, warmup schedules, and learning rate evaluation.
   * Best checkpoint selected automatically via hybrid MRR on validation sets and saved to `ft_minilm/`.

5. **Multi-Layered Guardrails & Anti-Hallucination**:
   * **Audience Filtering**: Prevents restricted internal staff articles from being used in public responses.
   * **Ask-First Gate**: Evaluates passage relevance before generation; automatically declines when evidence is missing.
   * **Post-Check Validation**: Regex and entity validation verify that all prices, dates, and order numbers in the generated text appear in the ground-truth sources.

---

## Repository Structure

```text
Deep-Learning-Chatbot-Final-Project/
│
├── grassroots-app.py                 # Interactive Streamlit concierge web application
├── Ticket_Chat_Bot.ipynb             # Full project notebook formatted for local execution (VS Code)
├── (Colab)Ticket_Chat_Bot.ipynb      # Full project notebook formatted for Google Colab
│
├── data/
│   ├── grassroots.db                 # SQLite database (customers, orders, order items)
│   ├── kb_docs.jsonl                 # Knowledge-base help-center articles (public & restricted)
│   ├── golden_questions.csv          # 35 labeled tuning questions with ground-truth answer spans
│   ├── answer_keys.json              # Grading rules and regex patterns for evaluation
│   ├── order_questions.json          # 10 live order benchmark questions
│   └── golden_heldout.csv            # Held-out evaluation questions
│
├── build_final_set.py                # Generator & validator script for comprehensive evaluation
├── golden_final.csv                  # 144-question expanded final test suite
├── answer_keys_final.json            # Answer keys & validation rules for final test suite
└── README.md                         # Project documentation
```

---

## Quick Start & Installation

### 1. Prerequisites
* **Python 3.10+**
* **[Ollama](https://ollama.com/)** running locally

### 2. Pull Local Language Models
Start Ollama and download the primary 3B assistant and 8B comparison model:
```bash
ollama pull llama3.2:3b
ollama pull llama3.1:8b
```

### 3. Install Dependencies
Clone the repository and install required packages:
```bash
git clone https://github.com/ZacharyZambrana/Deep-Learning-Chatbot-Final-Project.git
cd Deep-Learning-Chatbot-Final-Project

pip install sentence-transformers rank-bm25 openai streamlit torch pandas numpy
```

---

## Running the Streamlit App

Launch the interactive concierge web interface:
```bash
streamlit run grassroots-app.py
```
*or:*
```bash
python -m streamlit run grassroots-app.py
```

The application will open in your browser at `http://localhost:8501`.

### Interactive App Features:
* **"Signed in as" Dropdown (Sidebar)**: Toggle between authenticated customer accounts (`C-2041 - Dana Marlowe`, `C-3310 - Priya Nandakumar`, etc.) to demonstrate live database lookup and tenant security isolation.
* **Architecture Telemetry**: The sidebar shows live passage index counts, guardrail status, and read-only database connections.
* **Inspection Captions**: Each assistant message displays inference latency, prompt tokens, retrieved source IDs, and extracted memory state.

---

## Running the Notebooks

### Option A: Local Machine (VS Code)
* Open [`Ticket_Chat_Bot.ipynb`](file:///C:/Users/Zach/Desktop/Deep-Learning-Chatbot-Final-Project/Ticket_Chat_Bot.ipynb).
* Select your Python kernel.
* Connects automatically to local Ollama (`http://localhost:11434`) and local `data/` assets.
* Contains the complete development lifecycle: chunking strategy comparisons, hybrid fusion tuning, guardrail audits, MiniLM PyTorch fine-tuning, and the locked held-out evaluation suite.

### Option B: Google Colab
* Open [`(Colab)Ticket_Chat_Bot.ipynb`](file:///C:/Users/Zach/Desktop/Deep-Learning-Chatbot-Final-Project/(Colab)Ticket_Chat_Bot.ipynb) in Google Colab.
* The first cells automatically:
  1. Install Ollama and start the background daemon inside the Colab VM.
  2. Pull `llama3.2:3b` and `llama3.1:8b`.
  3. Clone or unzip repository assets and configure working paths seamlessly.

---

## Example Test Cases for Demos

| Scenario | Signed In As | Input Query | Expected Behavior |
| :--- | :--- | :--- | :--- |
| **Grounded Policy Search** | Any customer | *"What is the return freight deduction for a dining chair vs a sofa?"* | Cites `[KB-006]`: $35 per piece for dining chairs, $99 for sofas. |
| **Order Status Lookup** | `C-2041` (Dana) | *"On what date did I place order GF-40402?"* | Retrieves live record from SQLite: placed on `2026-09-28`. |
| **Conversational Memory** | `C-2041` (Dana) | *"What items are in that order?"* *(following above)* | Uses remembered `GF-40402` context to list Bouclé chairs and coffee table. |
| **Tenant Data Privacy** | `C-2041` (Dana) | *"Where is order GF-40377?"* | **Declined**: Order belongs to Priya (`C-3310`); Dana cannot view it. |
| **Authorized Access** | `C-3310` (Priya) | *"Where is order GF-40377?"* | **Answered**: Delivered `2026-09-21`, tracking `GFT-5530996538`. |
| **Anti-Hallucination** | Any customer | *"Where is order GF-49999?"* | **Declined**: Order does not exist; model safely refuses to fabricate data. |
