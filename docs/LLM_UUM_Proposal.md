# LLM UUM: Bilingual Hybrid RAG Document Intelligence System

**Course:** STTXK49512 Industrial Training  
**Session:** A252  
**Organization:** Computing Professional Enrichment & Development Division (CoPED), School of Computing, Universiti Utara Malaysia  
**Supervisor (Organization):** Mr. Mohd. Rushdi Idrus (Manager CoPED)  
**Student:** Ahmad Abbas Bin Abu Dzarr (Matric No. 301909)  
**Email:** abbasabudzarr@gmail.com | **Phone:** 011-56867018  

---

## Table of Contents
- [1.0 Introduction](#10-introduction)
  - [1.1 Project Background](#11-project-background)
  - [1.2 Problem Statement](#12-problem-statement)
  - [1.3 Objectives](#13-objectives)
  - [1.4 Scope](#14-scope)
  - [1.5 Project Significance](#15-project-significance)
- [2.0 Project Planning](#20-project-planning)
  - [2.1 Methodology](#21-methodology)
  - [2.2 Feasibility Study](#22-feasibility-study)
    - [2.2.1 Tools & Environment](#221-tools--environment)
    - [2.2.2 Cost Estimation](#222-cost-estimation)
    - [2.2.3 Gantt Chart](#223-gantt-chart)
- [3.0 Summary](#30-summary)
- [References](#references)
- [Appendixes](#appendixes)
  - [Appendix A: Use Case Description](#appendix-a--use-case-description)
  - [Appendix B: Proposal Endorsement & Sign-Off](#appendix-b--proposal-endorsement--sign-off)

---

## 1.0 Introduction

### 1.1 Project Background
Universiti Utara Malaysia (UUM) manages a large volume of official regulatory and academic documents across its administrative centres (Pusat Tanggungjawab, PTJ) and three academic colleges: UUM CAS, UUM COB, and UUM COLGIS, together with their graduate schools (AHSGS, OYAGSB, GSGSG) and sixteen constituent schools. These files include administrative circulars from the Research Management Centre (RMC) and Bursar's Office (Jabatan Bendahari), legal and commercial guidelines from ICC and JUU, undergraduate and postgraduate handbooks, academic calendars, and official application forms. Within the School of Computing, the Computing Professional Enrichment & Development Division (CoPED) builds internal software tools to support university operations and improve how staff and students access institutional data.

Large Language Models (LLMs) store general knowledge within their pretrained weights [2], [3], [6], [7], but standalone models perform poorly on specialized institutional tasks [1], [4]. They rely on static training data, cannot update their knowledge when university rules change, lack source attribution, and frequently hallucinate answers to regulatory questions [4]. To solve this, Lewis et al. [1] introduced Retrieval-Augmented Generation (RAG) [1], [5], [11], [12]. RAG pairs a generative model with an external document store [1], [5]. By retrieving relevant passages from authoritative files using dense semantic retrieval [5] and BM25 keyword matching [9] before generating a response, the system grounds its answers in verified text and allows updates to the knowledge base without retraining the model [10].

Operating a document assistant at UUM also requires handling queries in both Bahasa Melayu and English against documents written in either language. As Litschko et al. [8] showed in their work on Cross-Lingual Information Retrieval (CLIR), general multilingual models do not guarantee reliable cross-lingual retrieval without domain adaptation and section-level matching. This project builds LLM UUM at CoPED, combining PostgreSQL vector search (pgvector), keyword search (tsvector), metadata filtering, and cross-lingual alignment to deliver verified, traceable answers from official UUM files.

---

### 1.2 Problem Statement
Staff, researchers, and students at UUM currently look up rules, claim forms, and course requirements by manually checking scattered departmental web portals and long PDF documents. Building an automated assistant for this domain faces three main challenges:

1. **Scattered documents and hallucination in standalone models:** Official circulars, forms, and handbooks are split across different websites with inconsistent folder structures and naming schemes. Standard standalone LLMs cannot reliably answer questions about UUM regulations because they lack access to internal documents and cannot cite specific page numbers, circular numbers, or departments [1]–[4].

2. **Version lifecycles and cohort dependencies:** Similarity search alone is not enough for institutional rules. Administrative circulars follow an Active versus Superseded status, while academic handbooks apply only to a student's specific intake cohort. A pure vector search risks retrieving superseded circulars or applying graduation rules from the wrong academic year [1], [5].

3. **Mixed search needs and language mismatches:** User queries range from general questions to exact administrative codes like "RMC 008" or specific course codes. Users often write questions in English when the governing circular is in Bahasa Melayu, or vice versa. Keyword search alone fails on paraphrased or cross-lingual terms [9], while standard multilingual embeddings can lose accuracy across 100-page handbooks unless the documents are split into focused, section-level chunks [7], [8].

---

### 1.3 Objectives
The main objective of this project is to design, build, and evaluate LLM UUM, a bilingual (English and Bahasa Melayu) document intelligence system for CoPED that retrieves official UUM rules and provides answers with exact source citations.

Specific objectives:
1. Collect and organize official UUM circulars, academic handbooks, and forms across all PTJs and colleges into a standardized taxonomy with section-level chunks [8] and relational metadata (cohort year, school, category, and status).
2. Build a hybrid search engine in PostgreSQL combining dense vector retrieval (pgvector) [5], [10] with keyword matching (tsvector) [9], using a 60/40 rank fusion and bilingual term expansion [8].
3. Implement an answer generation pipeline that mirrors the user's language, excludes superseded circulars, asks for missing cohort information when needed, and cites the document title, circular number, department, and page number [1].
4. Evaluate retrieval accuracy and answer quality using standard information retrieval metrics (Recall@K, Precision@K, MRR, nDCG) [1], [8] and citation checks on representative UUM queries.

---

### 1.4 Scope
The scope of this project covers four main technical areas:

#### 1.4.1 Document Domain and Taxonomy
The system indexes official UUM documents across administrative departments (including RMC, Jabatan Bendahari, ICC, and JUU) and all three academic colleges: UUM CAS (7 schools: SOC, SOE, SAPSP, SMMTC, SCIMPA, SQS, and SLCP), UUM COB (5 schools: SBM, SEFB, TISSA-UUM, IBS, and STML), and UUM COLGIS (4 schools: SOL, SOIS, SOG, and STHEM), along with their graduate schools (AHSGS, OYAGSB, and GSGSG), the UUM Kuala Lumpur Campus (UUMKL), and college-wide repositories. To keep document ingestion consistent across portals, files are organized into five categories: `academic_calender`, `academic_handbooks`, `forms`, `postgrad_brochures`, and `undergrad_programs`.

#### 1.4.2 Document Processing and Localized Chunking
Large PDF documents (such as 100-page academic handbooks and multi-clause circulars) are extracted and split into focused, section-level chunks [8] covering specific topics like graduation rules, credit requirements, grading policies, and deferment procedures. Each chunk is converted into a vector embedding [5] and stored with its section heading and page number in PostgreSQL.

#### 1.4.3 Hybrid Retrieval, Cross-Lingual Matching, and Metadata Filtering
The search pipeline combines semantic search (PostgreSQL pgvector) [5], [10] to capture general meaning with keyword matching (PostgreSQL tsvector) [9] to catch exact form codes, course codes, and circular reference numbers. The two scores are combined using a 60/40 weighting:
$$\text{Score} = (0.60 \times \text{Semantic Score}) + (0.40 \times \text{Keyword Score})$$
tested against sample UUM questions. Cross-lingual retrieval between English and Bahasa Melayu is handled through multilingual sentence embeddings and bilingual term mapping [8]. Metadata filters narrow search results by document status (Active vs. Superseded), student cohort year, programme code, school, document category, edition, and language.

#### 1.4.4 Answer Generation, Clarification Handling, and Evaluation
The generation layer feeds retrieved passages into the LLM to produce responses grounded in official UUM documents, citing the document title, circular reference, issuing department, and page number. If a query lacks key context (such as a student's intake year or programme for graduation rules) or if no official file covers the topic, the system asks for clarification or reports the gap instead of guessing. System evaluation measures retrieval performance (Recall@K, Precision@K, MRR, nDCG) [1], [8] on bilingual test questions and checks citation accuracy in generated answers.

---

### 1.5 Project Significance
Building LLM UUM provides direct benefits for CoPED, administrative staff, and students:

1. **Verifiable answers:** Grounding answers in actual circular text prevents fabricated advice. Every response cites the official circular or handbook, department, and page number [1]–[4].
2. **Correct version and cohort handling:** Metadata filters ensure staff see active circulars rather than superseded rules, and students see curriculum requirements that match their entry cohort [5], [9].
3. **Bilingual support:** Multilingual embeddings and bilingual term mapping allow staff and students to ask questions in either English or Bahasa Melayu without worrying about the language of the source document [8].
4. **Straightforward maintenance:** Because the knowledge base lives in an external database, CoPED can update rules whenever new circulars or handbooks are published by re-indexing files, without retraining or fine-tuning models [1], [3].

---

## 2.0 Project Planning

### 2.1 Methodology
The project follows an Agile development approach across the 24-week industrial training period, organized into five main phases:

1. **Phase 1: Requirement Analysis and Taxonomy Standardization (Weeks 1 to 4):** Audit existing PTJ and college portals, establish the Master Tracker spreadsheet, and organize Google Drive repositories across all 16 UUM schools and administrative departments.
2. **Phase 2: Database Architecture and Docker Infrastructure Setup (Weeks 5 to 8):** Deploy containerized PostgreSQL 16 (pgvector) and n8n via Docker Compose, define relational tables, and set up HNSW vector indexes [10] and GIN full-text search indexes [9].
3. **Phase 3: Document Ingestion and Batch Vectorization Pipeline (Weeks 9 to 14):** Build Python ingestion scripts with PyMuPDF to parse PDFs, extract section-level chunks [8], generate embeddings [5], and tag entries with cohort year and active-status metadata.
4. **Phase 4: Hybrid Search, Cross-Lingual Expansion, and Multi-API Router (Weeks 15 to 19):** Implement the retrieval logic combining 60% semantic vector search [5], [10] with 40% BM25 keyword rank fusion [9], configure language-mirroring prompts, and set up Gemini-to-Groq fallback.
5. **Phase 5: n8n Workflow Integration, Testing, and Final Report (Weeks 20 to 24):** Build the n8n chat webhook workflow, evaluate retrieval accuracy (Recall@K, Precision@K, MRR) [1], [8] on bilingual test questions, and write the final industrial training report.

---

### 2.2 Feasibility Study

#### 2.2.1 Tools & Environment
- **Hardware:** Lenovo LOQ 5 laptop running Windows 11 with WSL2 Ubuntu Linux.
- **Containerization:** Docker and Docker Compose for local PostgreSQL and n8n services.
- **Database and Vector Store:** PostgreSQL 16 with pgvector (768-dimensional HNSW index) and tsvector (GIN index for keyword search).
- **Backend and Ingestion:** Python 3, PyMuPDF, Pandas, and psycopg2 for PDF extraction, chunking, and database indexing.
- **AI Models:** Google Gemini API (`text-embedding-004`, `gemini-1.5-flash`) as the primary engine, with Groq as an automated fallback.
- **Workflow and IDE:** n8n for visual workflow automation, Antigravity IDE, and VS Code.

#### 2.2.2 Cost Estimation
The system operates at zero software cost by using self-hosted open-source containers and permanent free-tier AI APIs. Storing documents in a local database also keeps confidential university files on-premises rather than sending them to third-party databases.

| Item | Component | Specification / Tier | Cost (RM) |
|---|---|---|---|
| 1 | Development Machine | Lenovo LOQ 5 (Existing Personal Hardware) | RM 0.00 |
| 2 | Operating System & WSL2 | Windows 11 Home + Ubuntu 22.04 LTS (WSL2) | RM 0.00 |
| 3 | Database & Vector Store | PostgreSQL 16 + pgvector (Dockerized, Open Source) | RM 0.00 |
| 4 | Workflow Engine | n8n (Community Self-Hosted via Docker) | RM 0.00 |
| 5 | AI API (Primary) | Google Gemini API (text-embedding-004, gemini-1.5-flash) Free Tier | RM 0.00 |
| 6 | AI API (Fallback) | Groq Cloud API (Free Developer Tier) | RM 0.00 |
| 7 | IDE & Dev Tools | VS Code, Antigravity IDE, Git (Open Source / Free) | RM 0.00 |
| **Total** | | | **RM 0.00** |

#### 2.2.3 Gantt Chart
The 24-week industrial training timeline spans Semester A252:

| Phase | Milestone / Key Activities | Weeks |
|---|---|---|
| **Phase 1** | Requirement Analysis, Document Auditing & Taxonomy Standardization | Weeks 1–4 |
| **Phase 2** | Database Architecture, Schema Design & Docker Infrastructure Setup | Weeks 5–8 |
| **Phase 3** | Document Ingestion Engine, PyMuPDF Chunking & Batch Vectorization | Weeks 9–14 |
| **Phase 4** | Hybrid Retrieval (pgvector + tsvector), Cross-Lingual & Multi-API Router | Weeks 15–19 |
| **Phase 5** | n8n Workflow Webhook, Bilingual IR Evaluation & Final Report | Weeks 20–24 |

---

## 3.0 Summary
This project builds and evaluates LLM UUM, an internal document intelligence system for the Computing Professional Enrichment & Development Division (CoPED) at Universiti Utara Malaysia. By combining PostgreSQL vector search (pgvector) [5], [10] and keyword search (tsvector) [9] with section-level chunking, bilingual query expansion [8], and metadata filtering for active circulars and student cohort years, the system gives staff and students fast, verified answers with exact page citations. Developed over a 24-week industrial training placement using locally containerized tools and permanent free-tier APIs, the platform keeps confidential university documents on-premises while providing a dependable reference system for UUM administrative and academic regulations.

---

## References
- **[1]** P. Lewis *et al.*, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, 2020, pp. 9459–9474.
- **[2]** F. Petroni *et al.*, "Language models as knowledge bases?," in *Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2019, pp. 2463–2473.
- **[3]** A. Roberts, C. Raffel, and N. Shazeer, "How much knowledge can you pack into the parameters of a language model?," in *Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2020, pp. 5418–5426.
- **[4]** G. Marcus, "The next decade in AI: Four steps towards robust artificial intelligence," *arXiv preprint arXiv:2002.06177*, 2020.
- **[5]** V. Karpukhin *et al.*, "Dense passage retrieval for open-domain question answering," in *Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2020, pp. 6769–6781.
- **[6]** A. Vaswani *et al.*, "Attention is all you need," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017.
- **[7]** J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of deep bidirectional transformers for language understanding," in *Proc. Conf. North American Chapter of the Association for Computational Linguistics (NAACL)*, 2019, pp. 4171–4186.
- **[8]** R. Litschko, I. Vulić, S. P. Ponzetto, and G. Glavaš, "On cross-lingual retrieval with multilingual sentence encoders," *Information Retrieval Journal*, vol. 25, no. 3, pp. 247–275, 2022.
- **[9]** S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Foundations and Trends in Information Retrieval*, vol. 3, no. 4, pp. 333–389, 2009.
- **[10]** Y. A. Malkov and D. A. Yashunin, "Efficient and robust approximate nearest neighbors using Hierarchical Navigable Small World graphs," *IEEE Transactions on Pattern Analysis and Machine Intelligence*, vol. 42, no. 4, pp. 824–836, 2020.
- **[11]** K. Guu, K. Lee, Z. Tung, P. Pasupat, and M.-W. Chang, "REALM: Retrieval-augmented language model pre-training," in *Proc. Int. Conf. Machine Learning (ICML)*, 2020, pp. 3929–3938.
- **[12]** K. Lee, M.-W. Chang, and K. Toutanova, "Latent retrieval for weakly supervised open domain question answering," in *Proc. 57th Annual Meeting of the Association for Computational Linguistics (ACL)*, 2019, pp. 6086–6096.

---

## Appendixes

### Appendix A: Use Case Description
- **Actor:** UUM Staff, Researcher, or Student
- **System:** LLM UUM (CoPED)
- **Primary Flows:**
  1. *Policy / Circular Query:* User asks about travel claim or research grant regulations -> System filters by Active circulars -> Hybrid search (pgvector + tsvector) -> LLM generates bilingual response citing Circular No., Issuing PTJ, and Page Number.
  2. *Academic Handbook / Cohort Query:* Student asks about graduation or credit transfer requirements -> System detects or requests student Cohort Year and Programme -> Retrieves relevant section-level handbook chunks -> LLM returns cohort-specific requirements with handbook edition and page reference.

### Appendix B: Proposal Endorsement & Sign-Off

**Prepared by:**  
Student: Ahmad Abbas Bin Abu Dzarr (Matric No. 301909)  
Signature: ____________________________________  
Date: ________________________  

**Endorsed by:**  
Supervisor: Mr. Mohd. Rushdi Idrus  
Position: Manager, Computing Professional Enrichment & Development Division (CoPED)  
Organization: School of Computing, Universiti Utara Malaysia  
Signature: ____________________________________  
Date: ________________________  

