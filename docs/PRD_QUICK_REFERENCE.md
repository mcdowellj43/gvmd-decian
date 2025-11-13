# Quick Reference Guide: Agent-Based Scanning PRD

**Navigation Guide for `PRODUCT_REQUIREMENTS_DOCUMENT.md`**

---

## 🎯 I Need To...

### **Understand What We're Building (5 min read)**

**→ Start Here:**
- **Section 1** (Executive Summary) - Problem, solution, success criteria
- **Section 2** (Product Overview) - The 3 components we're building
- **Section 5.1** (High-Level Architecture) - System diagram

**Key Takeaway:** Building 3 components (Agent Controller + Agent + gvmd Integration) for endpoint scanning via pull-based agents.

---

### **Get Technical Specifications (Engineers)**

**→ Go To:**

**For Backend (Agent Controller):**
- **Section 7.1** (Technology Stack) - Go, PostgreSQL, Redis
- **Section 7.1.2** (Database Schema) - Complete DDL with 6 tables
- **Section 7.1.3** (Job Queue) - Redis Streams implementation code
- **Section 8.1-8.3** (API Specifications) - All 3 APIs with endpoints

**For Agent Development:**
- **Section 7.2.1** (Technology Stack) - C, NASL interpreter, libcurl
- **Section 7.2.2** (NASL Interpreter) - Fork OpenVAS scanner
- **Section 7.2.3** (NVT Feed) - Feed sync mechanism, cache database
- **Section 7.2.4** (Configuration File) - agent.conf format (TOML)
- **Section 7.2.5** (Platform Requirements) - Linux/Windows/macOS specifics

**For Integration:**
- **Section 6.3** (gvmd Integration) - Agent installers, GSA UI, agent groups

---

### **Implement Specific Features**

**→ Jump To Requirement:**

**Agent Controller APIs:**
- **FR-AC-001** - Create scan endpoint (`POST /scans`)
- **FR-AC-002** - Get scan status (`GET /scans/{id}/status`)
- **FR-AC-003** - Get scan results (`GET /scans/{id}/results`)
- **FR-AC-004** - List agents (`GET /api/v1/admin/agents`)
- **FR-AC-005** - Update agents (`PATCH /api/v1/admin/agents`)
- **FR-AC-007** - Accept heartbeats (`POST /api/v1/agents/heartbeat`)
- **FR-AC-008** - Serve jobs (`GET /api/v1/agents/jobs`)
- **FR-AC-009** - Accept results (`POST /api/v1/agents/jobs/{id}/results`)

**Agent Features:**
- **FR-AGENT-001** - Registration flow
- **FR-AGENT-002** - Heartbeat loop with retry logic
- **FR-AGENT-003** - Job polling
- **FR-AGENT-004** - Local scanning with NASL
- **FR-AGENT-005** - NVT feed sync (rsync + GPG verification)
- **FR-AGENT-006** - Result submission with batching

**Each requirement includes:**
- ✅ Acceptance criteria checklist
- 📝 API contract examples
- 💻 Code snippets

---

### **Understand Data Flow (Architecture)**

**→ Read:**
- **Section 5.2** (Data Flow) - Complete scan creation flow (9 steps)
- **Section 5.3** (Component Responsibilities) - Who does what

**Flow Summary:**
```
User (GSA) → gvmd → Agent Controller → Job Queue
                                         ↓
                                     Agents poll
                                         ↓
                                   Execute locally
                                         ↓
                                   Submit results
                                         ↓
gvmd ← Agent Controller ← Results aggregated
  ↓
User sees report in GSA
```

---

### **Review API Contracts (Integration)**

**→ Section 8 (API Specifications)**

**Quick Navigation:**
- **8.1** - Scanner API (gvmd → Agent Controller)
- **8.2** - Admin API (gvmd → Agent Controller, needs API key)
- **8.3** - Agent API (Agents → Agent Controller, needs auth)
- **8.4** - Error response format

**Each API section includes:**
- Base path and authentication
- Complete endpoint table (method, path, status codes)
- Links to detailed requirements (Section 6)

---

### **Check Security Requirements (Security Team)**

**→ Section 9 (Security Requirements)**

**Must Review:**
- **SR-AUTH-001** - API key + JWT/mTLS authentication
- **SR-AUTH-002** - Agent authorization flow
- **SR-TLS-001** - Mandatory TLS 1.3
- **SR-TLS-002** - mTLS support (optional)
- **SR-DATA-001** - Encryption at rest
- **SR-VALID-001** - Input validation (injection prevention)
- **SR-AUDIT-001** - Security event logging

---

### **Plan Implementation (Project Manager)**

**→ Section 12 (Implementation Phases)**

**Phase 1 - MVP (Q2 2025, 12 weeks):**
- Go to **12.1** for scope, deliverables, timeline
- Success: 10 agents, 5 scans, results in GSA

**Phase 2 - Multi-Platform (Q3 2025, 10 weeks):**
- Go to **12.2** for Windows/macOS ports, agent groups, auto-update

**Phase 3 - Enterprise (Q4 2025, 12 weeks):**
- Go to **12.3** for HA, compliance, monitoring

**Each phase includes:**
- ☑️ Detailed scope checklist
- 📦 Deliverables list
- 📅 Week-by-week timeline
- ✅ Success criteria

---

### **Understand Performance Goals**

**→ Section 10 (Performance Requirements)**

**Critical Metrics:**
- **PR-SCALE-001** - 1,000 agents (MVP) → 10,000 agents (Phase 2)
- **PR-SCALE-002** - Database latency targets (< 10ms heartbeats)
- **PR-AVAIL-001** - 99.9% uptime SLA
- **PR-AGENT-001** - Agent resource limits (< 1% CPU idle, < 50% scanning)
- **PR-AGENT-002** - Scan duration targets (4 hours full scan)

---

### **Assess Risks (Product/Leadership)**

**→ Section 13 (Dependencies and Risks)**

**Critical Risks:**
- **13.1** - External dependencies (NVT feed, OpenVAS scanner)
- **13.2** - Technical risks (NASL complexity, scalability, security)
- **13.3** - Operational risks (deployment friction, performance impact)
- **13.4** - Business risks (license restrictions, competition)

**Each risk includes:**
- Likelihood + Impact rating
- Mitigation strategy

---

### **Make Architecture Decisions**

**→ Section 14 (Open Questions)**

**11 Questions to Decide:**
- **Q1** - Should Agent Controller cache NVT feed?
- **Q2** - Should agents buffer results offline?
- **Q4** - Should agents scan targets beyond localhost?
- **Q5** - Should we implement agent tags/labels?
- **Q7** - Database choice (PostgreSQL recommended)
- **Q8** - Authentication method (JWT + mTLS recommended)
- **Q9** - NASL interpreter (fork OpenVAS recommended)

**Each question includes:**
- Options A/B/C
- **Recommendation** with rationale

---

### **Look Up Definitions (Reference)**

**→ Appendix A (Glossary)**

**Common Terms:**
- **Agent** - Host-based daemon on endpoints
- **Agent Controller** - HTTP service bridging gvmd and agents
- **NVT** - Network Vulnerability Test (vulnerability test script)
- **NASL** - Scripting language for vulnerability tests
- **OID** - Unique identifier for NVTs (e.g., `1.3.6.1.4.1.25623.1.0.10662`)
- **Pull-Based Model** - Agents initiate connections (vs. push)

---

### **Find Code Evidence (Validation)**

**→ Appendix B (References)**

**Investigation Documents:**
- All 8 investigation docs listed
- Links to gvmd, gvm-libs, OpenVAS scanner repos
- Evidence of all claims in PRD

---

## 📊 Document Structure at a Glance

```
1. Executive Summary          ← Start here (big picture)
2. Product Overview            ← What we're building
3. Goals and Objectives        ← Why we're building it
4. User Personas               ← Who will use it
5. System Architecture         ← How it works (diagrams!)
6. Functional Requirements     ← 29 detailed features
7. Technical Requirements      ← Tech stack, database, code
8. API Specifications          ← All 3 APIs with examples
9. Security Requirements       ← Authentication, TLS, audit
10. Performance Requirements   ← Scalability, latency targets
11. Success Metrics            ← KPIs, benchmarks
12. Implementation Phases      ← 3-phase roadmap
13. Dependencies and Risks     ← What could go wrong
14. Open Questions             ← Decisions needed
Appendix A: Glossary          ← Define terms
Appendix B: References        ← Source documents
```

---

## 🚀 Quick Start Paths

### **Path 1: I'm an Engineer - Show Me Code**
1. Read **Section 2** (Product Overview) - 5 min
2. Jump to **Section 7** (Technical Requirements) - 20 min
3. Pick a requirement in **Section 6** - Start coding
4. Reference **Section 8** (APIs) as needed

**Total Time:** 30 minutes → Start building

---

### **Path 2: I'm a PM - Give Me Timeline**
1. Read **Section 1** (Executive Summary) - 3 min
2. Read **Section 12** (Implementation Phases) - 10 min
3. Review **Section 11** (Success Metrics) - 5 min
4. Check **Section 13** (Risks) - 10 min

**Total Time:** 30 minutes → Ready to plan

---

### **Path 3: I'm a Stakeholder - Sell Me**
1. Read **Section 1** (Executive Summary) - 3 min
2. Read **Section 2.1** (What We're Building) - 2 min
3. Read **Section 3** (Goals and Objectives) - 5 min
4. Skim **Section 5.1** (Architecture diagram) - 2 min
5. Read **Section 12.1** (Phase 1 MVP scope) - 5 min

**Total Time:** 15 minutes → Understand value

---

### **Path 4: I'm Security - Audit This**
1. Read **Section 2** (Product Overview) - 5 min
2. Read **Section 9** (Security Requirements) - 20 min
3. Check **Section 7.2.5** (Agent runs as root) - 5 min
4. Review **Section 13.2** (Security risks) - 10 min
5. Check **Section 8** (API authentication) - 10 min

**Total Time:** 50 minutes → Security assessment

---

## 📍 Common Lookups

| I need to find... | Go to... |
|-------------------|----------|
| Database schema | Section 7.1.2 |
| API endpoints | Section 8 |
| Agent config file format | Section 7.2.4 |
| NVT feed sync process | Section 7.2.3, FR-AGENT-005 |
| Heartbeat flow | FR-AGENT-002 |
| Scan execution flow | Section 5.2, FR-AGENT-004 |
| Job queue implementation | Section 7.1.3 |
| Timeline and milestones | Section 12 |
| Technology stack decisions | Section 7.1, 7.2 |
| Error handling | Section 8.4 |

---

## 💡 Pro Tips

**Use Section Numbers:**
- Every requirement has an ID (e.g., `FR-AC-001`)
- Easy to reference in tickets: "Implement FR-AC-001"

**Follow Links:**
- Requirements link to APIs
- APIs link back to requirements
- Everything is cross-referenced

**Code Examples:**
- Every API has request/response JSON
- Database schema has complete DDL
- Job queue has Go implementation

**Copy-Paste Ready:**
- Configuration files are complete
- API contracts are exact
- Database schemas are executable

---

## 📝 How to Use This PRD

**For Tickets/Issues:**
```markdown
## User Story
As defined in FR-AC-001 (Section 6.1)

## Acceptance Criteria
- [ ] Endpoint POST /scans accepts JSON payload
- [ ] Returns HTTP 201 with scan_id
- [ ] Validates agent UUIDs
- [ ] Queues jobs for each agent

## API Contract
See Section 8.1 for complete request/response format

## References
- Architecture: Section 5.2 (Data Flow)
- Database: Section 7.1.2 (scans table)
- Error Handling: Section 8.4
```

**For Design Docs:**
- Reference PRD sections instead of duplicating
- Example: "Authentication per SR-AUTH-001"

**For Code Reviews:**
- Check against acceptance criteria
- Validate API matches Section 8 specs
- Ensure security per Section 9

---

**Questions? Confused?**
- Start with **Section 1** (Executive Summary)
- Check **Appendix A** (Glossary) for terms
- Review **Section 5.1** (Architecture diagram)

**Ready to build?**
- Engineers: **Section 7** (Technical Requirements)
- PMs: **Section 12** (Implementation Phases)
- Stakeholders: **Section 1-3** (Overview & Goals)
