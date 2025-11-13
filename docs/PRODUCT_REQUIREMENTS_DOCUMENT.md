# Product Requirements Document: Agent-Based Vulnerability Scanning System

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Status:** Draft for Review
**Product Owner:** [Your Name]
**Engineering Lead:** [To Be Assigned]

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Overview](#2-product-overview)
3. [Goals and Objectives](#3-goals-and-objectives)
4. [User Personas](#4-user-personas)
5. [System Architecture](#5-system-architecture)
6. [Functional Requirements](#6-functional-requirements)
7. [Technical Requirements](#7-technical-requirements)
8. [API Specifications](#8-api-specifications)
9. [Security Requirements](#9-security-requirements)
10. [Performance Requirements](#10-performance-requirements)
11. [Success Metrics](#11-success-metrics)
12. [Implementation Phases](#12-implementation-phases)
13. [Dependencies and Risks](#13-dependencies-and-risks)
14. [Open Questions](#14-open-questions)

---

## 1. Executive Summary

### 1.1 Problem Statement

Organizations need to perform vulnerability assessments on endpoints (servers, workstations, IoT devices) that are:
- Behind firewalls (no inbound access)
- On dynamic IPs (DHCP environments)
- Mobile or intermittently connected
- Requiring privileged local access for comprehensive scanning

Traditional network-based scanning cannot effectively reach or assess these endpoints.

### 1.2 Proposed Solution

Build an **agent-based vulnerability scanning system** that integrates with Greenbone Vulnerability Management (gvmd) to enable:
- **Host-based agents** deployed on endpoints
- **Pull-based polling model** (agents initiate connections)
- **Local privilege scanning** (full system access)
- **Centralized management** via gvmd's existing GMP interface

### 1.3 Success Criteria

- ✅ Agents successfully register with Agent Controller
- ✅ Scans created in gvmd are executed on target agents
- ✅ Results are returned to gvmd and displayed in UI
- ✅ System supports 1000+ concurrent agents
- ✅ Compatible with existing OpenVAS NVT feed
- ✅ Agent deployment on Windows, Linux, macOS

### 1.4 Target Delivery

**Phase 1 (MVP):** Q2 2025 - Core functionality (single OS, basic scanning)
**Phase 2 (Multi-Platform):** Q3 2025 - All OS support, auto-updates
**Phase 3 (Enterprise):** Q4 2025 - High availability, compliance reporting

---

## 2. Product Overview

### 2.1 What We're Building

**Three interconnected components:**

1. **Agent Controller Service** - HTTP REST service that bridges gvmd and agents
2. **Host-Based Agent** - Lightweight daemon deployed on endpoints
3. **Agent Installer Distribution** - Mechanism to deliver agent installers via gvmd

### 2.2 Key Features

#### Agent Controller Service
- RESTful API with three distinct interfaces (Scanner API, Admin API, Agent API)
- Job queue management (assign scans to agents)
- Agent status tracking (online/offline/inactive)
- Result aggregation (collect findings from multiple agents)
- Configuration management (push settings to agents)

#### Host-Based Agent
- Pull-based polling (phone home every 10 minutes)
- NASL interpreter (execute OpenVAS vulnerability tests)
- NVT feed sync (daily updates from Greenbone feed)
- Local scanning (privileged access to localhost)
- Auto-update capability (agent binary updates)

#### Integration with gvmd
- Works with existing gvmd installation (no gvmd code changes)
- Uses gvmd's scanner management interface
- Compatible with existing GMP clients (GSA web UI, CLI)
- Supports agent installer distribution via GMP commands

### 2.3 What We're NOT Building

❌ Network-based scanning (that's OpenVAS scanner's job)
❌ Custom vulnerability tests (we use OpenVAS NVT feed)
❌ Agent UI (agents are headless daemons)
❌ gvmd modifications (we integrate, not modify)
❌ Custom reporting (gvmd handles reports)

---

## 3. Goals and Objectives

### 3.1 Business Goals

**Primary Goals:**
1. Enable vulnerability scanning of endpoints behind firewalls
2. Provide comprehensive host-based assessments with privileged access
3. Scale to enterprise environments (10,000+ endpoints)
4. Maintain compatibility with Greenbone ecosystem

**Secondary Goals:**
1. Support compliance scanning (CIS benchmarks, STIG)
2. Enable continuous monitoring (always-on agents)
3. Reduce network bandwidth (local scanning vs. remote)
4. Support air-gapped environments (offline agents)

### 3.2 User Goals

**Security Administrators:**
- Deploy agents quickly across fleet
- Monitor agent health (online/offline status)
- Schedule recurring scans on endpoints
- View consolidated vulnerability reports

**Compliance Officers:**
- Audit endpoint configurations
- Track remediation progress
- Generate compliance reports (PCI-DSS, HIPAA, SOC2)

**IT Operations:**
- Minimal performance impact on endpoints
- Automated agent updates
- Centralized agent management

### 3.3 Technical Goals

**Reliability:**
- 99.9% agent uptime
- Automatic reconnection after network outages
- Graceful handling of controller downtime

**Scalability:**
- Support 10,000+ concurrent agents per controller
- Horizontal scaling (multiple controllers)
- Efficient job distribution

**Security:**
- Encrypted communication (TLS 1.3)
- Mutual authentication (client certificates)
- No inbound ports required on agents

---

## 4. User Personas

### 4.1 Primary Personas

#### Security Administrator (Sarah)
**Role:** Vulnerability Management Lead
**Goals:** Scan all corporate assets, track vulnerabilities, meet compliance
**Pain Points:** Can't scan remote workers, limited visibility into endpoints
**Use Cases:**
- Deploy agents to 500 laptops
- Create scan targeting "All Remote Workers" agent group
- Review findings in GSA web interface

#### System Engineer (Mike)
**Role:** Linux System Administrator
**Goals:** Install agents on production servers, minimize downtime
**Pain Points:** Complex deployment, performance impact concerns
**Use Cases:**
- Install agent on Ubuntu servers via Ansible
- Configure agent to scan during maintenance window (cron schedule)
- Monitor agent resource usage

### 4.2 Secondary Personas

#### Compliance Auditor (Carlos)
**Role:** IT Compliance Officer
**Goals:** Prove endpoint compliance, generate audit reports
**Use Cases:**
- Run CIS Benchmark scans on all Windows servers
- Export compliance reports for auditors

#### DevOps Engineer (Priya)
**Role:** Cloud Infrastructure Engineer
**Goals:** Automate agent deployment in AWS/Azure
**Use Cases:**
- Include agent in base AMI/VM image
- Auto-register agents on instance boot
- Tag agents by environment (dev/staging/prod)

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         User Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   GSA Web    │  │   gvm-cli    │  │  GMP Clients │       │
│  │   Interface  │  │   (CLI Tool) │  │   (Custom)   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    GMP Protocol (XML over TLS)
                             │
┌────────────────────────────┼──────────────────────────────────┐
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────────┐      │
│  │                       gvmd                           │      │
│  │  (Greenbone Vulnerability Manager Daemon)           │      │
│  │                                                      │      │
│  │  - Task management                                  │      │
│  │  - Scan configuration                               │      │
│  │  - Report aggregation                               │      │
│  │  - User authentication                              │      │
│  └──────────────┬────────────────────┬─────────────────┘      │
│                 │                    │                         │
│        HTTP Scanner API       Admin API                        │
│        (POST /scans)          (PATCH /agents)                  │
│                 │                    │                         │
└─────────────────┼────────────────────┼─────────────────────────┘
                  │                    │
                  └────────────────────┘
                           │
                  HTTP/HTTPS (REST)
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │          Agent Controller Service                   │     │
│  │                                                     │     │
│  │  Components:                                        │     │
│  │  ├── API Gateway (3 interfaces)                    │     │
│  │  ├── Job Queue Manager                             │     │
│  │  ├── Agent Registry                                │     │
│  │  ├── Result Aggregator                             │     │
│  │  └── Configuration Store                           │     │
│  │                                                     │     │
│  │  Exposes:                                          │     │
│  │  - Scanner API (gvmd → controller)                │     │
│  │  - Admin API (gvmd → controller)                  │     │
│  │  - Agent API (agents → controller)                │     │
│  └──────────────────────┬──────────────────────────────┘     │
│                         │                                     │
│                 Agent-Facing API                             │
│                 (POST /heartbeat)                            │
│                 (GET /jobs)                                  │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          │
                 HTTP/HTTPS (REST)
                          │
          ┌───────────────┴───────────────┐
          │                               │
┌─────────▼─────────┐         ┌──────────▼──────────┐
│   Agent (Linux)   │         │  Agent (Windows)    │
│                   │         │                     │
│  ┌──────────────┐ │         │  ┌──────────────┐  │
│  │ Polling Loop │ │         │  │ Polling Loop │  │
│  ├──────────────┤ │         │  ├──────────────┤  │
│  │ NASL Engine  │ │         │  │ NASL Engine  │  │
│  ├──────────────┤ │         │  ├──────────────┤  │
│  │ NVT Feed     │ │         │  │ NVT Feed     │  │
│  │ (local)      │ │         │  │ (local)      │  │
│  └──────────────┘ │         │  └──────────────┘  │
│                   │         │                     │
│  Scans:           │         │  Scans:             │
│  localhost        │         │  localhost          │
└───────────────────┘         └─────────────────────┘
```

### 5.2 Data Flow: Creating and Executing a Scan

```
1. User creates scan in GSA
   └─> GMP: <create_task>
   └─> gvmd stores task

2. User starts scan
   └─> GMP: <start_task>
   └─> gvmd: POST /scans to Agent Controller
       {
         "vts": ["1.3.6.1.4.1.25623.1.0.10662", ...],
         "agents": ["agent-uuid-1", "agent-uuid-2"],
         "targets": [{"hosts": "localhost", ...}],
         "preferences": {...}
       }

3. Agent Controller queues jobs
   └─> Job Queue:
       - job-1 for agent-uuid-1
       - job-2 for agent-uuid-2

4. Agent polls for work (every 10 minutes)
   Agent-1: GET /api/v1/agents/jobs
   └─> Agent Controller: [job-1]

   Agent-1 downloads job:
   └─> {
         "job_id": "job-1",
         "vts": ["1.3.6.1.4.1.25623.1.0.10662", ...],
         "targets": [{"hosts": "localhost", ...}]
       }

5. Agent executes scan locally
   └─> For each VT OID:
       - Lookup OID in local NVT database
       - Load .nasl script from disk
       - Execute with NASL interpreter
       - Collect results

6. Agent submits results
   Agent-1: POST /api/v1/agents/jobs/job-1/results
   └─> {
         "results": [
           {
             "nvt_oid": "1.3.6.1.4.1.25623.1.0.10662",
             "host": "localhost",
             "port": "22/tcp",
             "severity": 5.0,
             "description": "OpenSSH 7.4 detected (obsolete)"
           }
         ]
       }

7. Agent Controller aggregates results
   └─> Combines results from agent-1 and agent-2

8. gvmd polls for results
   gvmd: GET /scans/{scan_id}/results
   └─> Agent Controller returns aggregated results

9. User views report in GSA
   └─> gvmd formats report
   └─> GSA displays findings
```

### 5.3 Component Responsibilities

#### gvmd (Existing Component - No Modifications)
- User authentication and authorization
- Task/scan configuration storage
- Target and credential management
- Report generation and storage
- GMP API server

#### Agent Controller Service (New Component - To Build)
- Accept scan requests from gvmd (Scanner API)
- Manage agent registry (Admin API)
- Queue jobs for agents
- Track agent status (heartbeat monitoring)
- Aggregate scan results from multiple agents
- Serve jobs to agents (Agent API)
- Distribute configuration updates

#### Host-Based Agent (New Component - To Build)
- Register with Agent Controller on first run
- Send periodic heartbeats (default: 10 minutes)
- Poll for assigned scan jobs
- Sync NVT feed from Greenbone (daily)
- Execute vulnerability scans locally
- Submit results to Agent Controller
- Apply configuration updates

---

## 6. Functional Requirements

### 6.1 Agent Controller Service

#### FR-AC-001: Scanner API - Accept Scan Requests
**Priority:** P0 (Must Have)
**User Story:** As gvmd, I want to create scans on the Agent Controller so that agents can execute them.

**Acceptance Criteria:**
- [ ] Exposes `POST /{prefix}/scans` endpoint (default: `/scans`)
- [ ] Accepts JSON payload with VT list, agents, targets, preferences
- [ ] Returns HTTP 201 Created with scan_id
- [ ] Validates payload (required fields, valid agent UUIDs)
- [ ] Queues jobs for each specified agent
- [ ] Stores scan metadata in database

**API Contract:**
```http
POST /scans HTTP/1.1
Content-Type: application/json

{
  "vts": [
    {"vt_id": "1.3.6.1.4.1.25623.1.0.10662", "preferences": {...}}
  ],
  "agents": [
    {"agent_id": "550e8400-...", "hostname": "server1.example.com"}
  ],
  "targets": [
    {"hosts": "localhost", "ports": "1-65535", "credentials": {...}}
  ],
  "scanner_preferences": {
    "max_checks": "4",
    "max_hosts": "20"
  }
}

Response: HTTP 201 Created
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "agents_assigned": 1
}
```

#### FR-AC-002: Scanner API - Provide Scan Status
**Priority:** P0 (Must Have)
**User Story:** As gvmd, I want to check scan progress so I can update the task status in the UI.

**Acceptance Criteria:**
- [ ] Exposes `GET /{prefix}/scans/{scan_id}/status` endpoint
- [ ] Returns overall scan status (queued/running/completed/failed)
- [ ] Returns per-agent progress (agents_total, agents_running, agents_completed)
- [ ] Returns progress percentage (0-100)
- [ ] Updates in real-time as agents report status

**API Contract:**
```http
GET /scans/550e8400-e29b-41d4-a716-446655440000/status HTTP/1.1

Response: HTTP 200 OK
{
  "scan_id": "550e8400-...",
  "status": "running",
  "progress": 45,
  "agents_total": 3,
  "agents_running": 2,
  "agents_completed": 1,
  "agents_failed": 0,
  "start_time": 1705318200,
  "end_time": null
}
```

#### FR-AC-003: Scanner API - Provide Scan Results
**Priority:** P0 (Must Have)
**User Story:** As gvmd, I want to retrieve scan results so I can generate reports for users.

**Acceptance Criteria:**
- [ ] Exposes `GET /{prefix}/scans/{scan_id}/results` endpoint
- [ ] Supports pagination via `?range=0-99` query parameter
- [ ] Returns results in OpenVAS-compatible JSON format
- [ ] Aggregates results from all agents in scan
- [ ] Includes agent_id/hostname in each result
- [ ] Returns total_results count

**API Contract:**
```http
GET /scans/550e8400-e29b-41d4-a716-446655440000/results?range=0-99 HTTP/1.1

Response: HTTP 200 OK
{
  "results": [
    {
      "result_id": "result-001",
      "agent_id": "550e8400-...",
      "agent_hostname": "server1.example.com",
      "nvt": {
        "oid": "1.3.6.1.4.1.25623.1.0.12345",
        "name": "OpenSSH Obsolete Version Detection",
        "severity": 5.0,
        "cvss_base_vector": "AV:N/AC:L/Au:N/C:N/I:N/A:N"
      },
      "host": "localhost",
      "port": "22/tcp",
      "threat": "Medium",
      "description": "The remote SSH server is running an obsolete version.",
      "qod": 80
    }
  ],
  "total_results": 245,
  "returned_results": 100
}
```

#### FR-AC-004: Admin API - List Agents
**Priority:** P0 (Must Have)
**User Story:** As gvmd, I want to list all registered agents so I can display them in the UI.

**Acceptance Criteria:**
- [ ] Exposes `GET /api/v1/admin/agents` endpoint
- [ ] Requires API key authentication
- [ ] Returns all registered agents with status
- [ ] Includes agent metadata (hostname, OS, IPs, version)
- [ ] Includes connection status (online/offline/inactive)
- [ ] Includes last_heartbeat timestamp

**API Contract:**
```http
GET /api/v1/admin/agents HTTP/1.1
X-API-Key: <api-key>

Response: HTTP 200 OK
{
  "agents": [
    {
      "agent_id": "550e8400-...",
      "hostname": "server1.example.com",
      "connection_status": "online",
      "last_heartbeat": 1705318500,
      "ip_addresses": ["192.168.1.100", "10.0.0.50"],
      "operating_system": "Ubuntu 22.04 LTS",
      "architecture": "amd64",
      "agent_version": "1.0.0",
      "authorized": true
    }
  ],
  "total": 1
}
```

#### FR-AC-005: Admin API - Update Agents
**Priority:** P0 (Must Have)
**User Story:** As an admin, I want to authorize/deauthorize agents so I can control which agents can execute scans.

**Acceptance Criteria:**
- [ ] Exposes `PATCH /api/v1/admin/agents` endpoint
- [ ] Requires API key authentication
- [ ] Accepts bulk agent updates (multiple agents at once)
- [ ] Supports updating: authorized, update_to_latest flags
- [ ] Returns count of updated/failed agents
- [ ] Signals config_updated to agents on next heartbeat

**API Contract:**
```http
PATCH /api/v1/admin/agents HTTP/1.1
X-API-Key: <api-key>
Content-Type: application/json

{
  "agents": [
    {
      "agent_id": "550e8400-...",
      "authorized": true,
      "update_to_latest": true
    }
  ]
}

Response: HTTP 200 OK
{
  "updated": 1,
  "failed": 0,
  "errors": []
}
```

#### FR-AC-006: Admin API - Delete Agents
**Priority:** P1 (Should Have)
**User Story:** As an admin, I want to decommission agents so they stop polling for work.

**Acceptance Criteria:**
- [ ] Exposes `POST /api/v1/admin/agents/delete` endpoint
- [ ] Requires API key authentication
- [ ] Accepts list of agent IDs to delete
- [ ] Marks agents for deletion (soft delete)
- [ ] Agents receive decommission signal on next heartbeat
- [ ] Agents clean up and stop polling

**API Contract:**
```http
POST /api/v1/admin/agents/delete HTTP/1.1
X-API-Key: <api-key>
Content-Type: application/json

{
  "agent_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}

Response: HTTP 200 OK
{
  "deleted": 2,
  "failed": 0
}
```

#### FR-AC-007: Agent API - Accept Heartbeats
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to send heartbeats so the controller knows I'm online.

**Acceptance Criteria:**
- [ ] Exposes `POST /api/v1/agents/heartbeat` endpoint
- [ ] Requires agent authentication (token or mTLS)
- [ ] Accepts agent status update (version, IPs, OS, etc.)
- [ ] Updates agent last_heartbeat timestamp
- [ ] Returns config_updated flag if configuration changed
- [ ] Registers new agents on first heartbeat

**API Contract:**
```http
POST /api/v1/agents/heartbeat HTTP/1.1
Authorization: Bearer <agent-token>
Content-Type: application/json

{
  "agent_id": "550e8400-...",
  "hostname": "server1.example.com",
  "connection_status": "active",
  "ip_addresses": ["192.168.1.100", "10.0.0.50"],
  "agent_version": "1.0.0",
  "operating_system": "Ubuntu 22.04 LTS",
  "architecture": "amd64"
}

Response: HTTP 200 OK
{
  "status": "accepted",
  "config_updated": false,
  "next_heartbeat_in_seconds": 600,
  "authorized": true
}
```

#### FR-AC-008: Agent API - Serve Jobs to Agents
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to poll for scan jobs so I can execute vulnerability scans.

**Acceptance Criteria:**
- [ ] Exposes `GET /api/v1/agents/jobs` endpoint
- [ ] Requires agent authentication
- [ ] Returns jobs assigned to requesting agent
- [ ] Returns empty array if no jobs available
- [ ] Includes full scan configuration in job
- [ ] Marks jobs as "assigned" when retrieved

**API Contract:**
```http
GET /api/v1/agents/jobs HTTP/1.1
Authorization: Bearer <agent-token>
X-Agent-ID: 550e8400-...

Response: HTTP 200 OK
{
  "jobs": [
    {
      "job_id": "job-12345",
      "scan_id": "550e8400-...",
      "job_type": "vulnerability_scan",
      "priority": "normal",
      "created_at": "2025-01-15T10:25:00Z",
      "config": {
        "vts": [
          {"vt_id": "1.3.6.1.4.1.25623.1.0.10662", "preferences": {...}}
        ],
        "targets": [
          {"hosts": "localhost", "ports": "1-65535"}
        ],
        "scanner_preferences": {
          "max_checks": "4"
        }
      }
    }
  ]
}
```

#### FR-AC-009: Agent API - Accept Results
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to submit scan results so they're available to gvmd.

**Acceptance Criteria:**
- [ ] Exposes `POST /api/v1/agents/jobs/{job_id}/results` endpoint
- [ ] Requires agent authentication
- [ ] Accepts results in OpenVAS-compatible format
- [ ] Stores results in database linked to scan_id
- [ ] Updates scan progress
- [ ] Returns HTTP 202 Accepted

**API Contract:**
```http
POST /api/v1/agents/jobs/job-12345/results HTTP/1.1
Authorization: Bearer <agent-token>
Content-Type: application/json

{
  "job_id": "job-12345",
  "scan_id": "550e8400-...",
  "agent_id": "550e8400-...",
  "status": "completed",
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:45:00Z",
  "results": [
    {
      "nvt": {
        "oid": "1.3.6.1.4.1.25623.1.0.12345",
        "name": "OpenSSH Obsolete Version Detection",
        "severity": 5.0
      },
      "host": "localhost",
      "port": "22/tcp",
      "threat": "Medium",
      "description": "The remote SSH server is running an obsolete version."
    }
  ]
}

Response: HTTP 202 Accepted
{
  "status": "accepted",
  "results_received": 1
}
```

#### FR-AC-010: Configuration Management
**Priority:** P1 (Should Have)
**User Story:** As an admin, I want to update agent configuration globally so all agents apply new settings.

**Acceptance Criteria:**
- [ ] Exposes `GET/PUT /api/v1/admin/scan-agent-config` endpoints
- [ ] Supports heartbeat interval, retry policy, bulk settings
- [ ] Agents fetch config on startup and when config_updated=true
- [ ] Configuration validated before applying
- [ ] Per-agent overrides supported

**Configuration Schema:**
```json
{
  "heartbeat": {
    "interval_in_seconds": 600,
    "miss_until_inactive": 1
  },
  "retry": {
    "attempts": 5,
    "delay_in_seconds": 60,
    "max_jitter_in_seconds": 30
  },
  "agent_script_executor": {
    "bulk_size": 100,
    "bulk_throttle_time_in_ms": 1000,
    "scheduler_cron_time": ["0 2 * * *"]
  }
}
```

### 6.2 Host-Based Agent

#### FR-AGENT-001: Agent Registration
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to register with the Agent Controller on first startup so I can receive scan jobs.

**Acceptance Criteria:**
- [ ] Agent generates UUID on first run if not configured
- [ ] Agent sends initial heartbeat with full system info
- [ ] Agent stores assigned agent_id locally
- [ ] Agent waits for admin authorization before accepting jobs
- [ ] Agent displays registration status in logs

**Flow:**
```
1. Agent starts for first time
2. Reads config file: /etc/gvm-agent/agent.conf
   - controller_url: https://controller.example.com
   - auth_token: <token from installation>
3. Generates agent_id if not present
4. POST /api/v1/agents/heartbeat (first registration)
5. Agent Controller stores agent record
6. Admin authorizes agent via gvmd UI
7. Next heartbeat returns: authorized=true
8. Agent begins polling for jobs
```

#### FR-AGENT-002: Periodic Heartbeat
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to send heartbeats periodically so the controller knows I'm online.

**Acceptance Criteria:**
- [ ] Agent sends heartbeat every N seconds (default: 600)
- [ ] Heartbeat includes current system info (IPs, hostname, version)
- [ ] Heartbeat interval configurable via config
- [ ] Agent retries with exponential backoff on failure
- [ ] Agent logs heartbeat success/failure

**Retry Logic:**
```
Attempt 1: Send heartbeat
  └─ Failed → Wait 60s + random(0-30s)
Attempt 2: Send heartbeat
  └─ Failed → Wait 120s + random(0-30s)
Attempt 3: Send heartbeat
  └─ Failed → Wait 240s + random(0-30s)
Attempt 4: Send heartbeat
  └─ Failed → Wait 480s + random(0-30s)
Attempt 5: Send heartbeat
  └─ Failed → Give up, wait for next interval
```

#### FR-AGENT-003: Job Polling
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to poll for scan jobs during heartbeat so I can execute vulnerability scans.

**Acceptance Criteria:**
- [ ] Agent calls GET /api/v1/agents/jobs after each heartbeat
- [ ] Agent downloads full job configuration
- [ ] Agent validates job (has required VTs, valid targets)
- [ ] Agent executes one job at a time (no concurrency)
- [ ] Agent logs job start/completion

**Flow:**
```
Every 10 minutes:
  1. POST /api/v1/agents/heartbeat
     └─ Response: {authorized: true, config_updated: false}

  2. GET /api/v1/agents/jobs
     └─ Response: {jobs: [job-12345]}

  3. For each job:
     - Validate job config
     - Check if NVT feed is current
     - Execute scan (see FR-AGENT-004)
     - Submit results

  4. Sleep (600s + random jitter)
  5. Repeat
```

#### FR-AGENT-004: Local Vulnerability Scanning
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to execute vulnerability scans against localhost so I can detect security issues.

**Acceptance Criteria:**
- [ ] Agent includes NASL interpreter (OpenVAS scanner fork)
- [ ] Agent has local NVT feed (/opt/gvm-agent/plugins/)
- [ ] Agent executes VTs by OID against localhost
- [ ] Agent applies VT preferences from job config
- [ ] Agent applies scanner preferences (max_checks, etc.)
- [ ] Agent collects results in OpenVAS format
- [ ] Agent logs scan progress

**Execution Flow:**
```python
def execute_scan(job):
    results = []

    # For each VT in job
    for vt in job['config']['vts']:
        oid = vt['vt_id']
        preferences = vt['preferences']

        # Lookup OID in local NVT database
        nvt_record = db.get_nvt_by_oid(oid)
        script_path = nvt_record['filename']

        # Load NASL script
        script_content = read_file(script_path)

        # Set preferences
        for pref_id, value in preferences.items():
            set_kb_item(f"{oid}/{pref_id}", value)

        # Execute NASL script
        result = nasl_interpreter.execute(
            script=script_content,
            target="localhost",
            port_list=job['config']['targets'][0]['ports']
        )

        # Collect results
        if result.findings:
            results.extend(result.findings)

    return results
```

#### FR-AGENT-005: NVT Feed Synchronization
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to sync the NVT feed regularly so I have the latest vulnerability tests.

**Acceptance Criteria:**
- [ ] Agent syncs NVT feed on first startup
- [ ] Agent syncs feed daily (cron schedule from config)
- [ ] Agent supports rsync and HTTP feed sources
- [ ] Agent verifies GPG signatures on feed
- [ ] Agent rebuilds OID index after sync
- [ ] Agent logs feed sync status

**Sync Flow:**
```bash
# Daily sync (configured via scheduler_cron_time)
# Default: "0 2 * * *" (2 AM daily)

1. Check feed source:
   - rsync://feed.community.greenbone.net/nvt-feed
   - OR https://controller.example.com/api/v1/agents/feed

2. Sync feed to local directory:
   rsync -av rsync://feed.community.greenbone.net/nvt-feed \
     /opt/gvm-agent/plugins/

3. Verify GPG signature:
   gpg --verify /opt/gvm-agent/plugins/sha256sums.asc

4. Rebuild OID index:
   sqlite3 /var/lib/gvm-agent/nvt_cache.db <<EOF
   DELETE FROM nvts;
   INSERT INTO nvts (oid, filename, name, family)
     SELECT ... FROM nasl_parse_all();
   EOF

5. Log sync completion:
   [2025-01-15 02:15:23] INFO: NVT feed sync completed
   [2025-01-15 02:15:23] INFO: 95,432 NVTs indexed
```

#### FR-AGENT-006: Result Submission
**Priority:** P0 (Must Have)
**User Story:** As an agent, I want to submit scan results to the controller so gvmd can display them.

**Acceptance Criteria:**
- [ ] Agent formats results in OpenVAS JSON format
- [ ] Agent includes agent_id and hostname in results
- [ ] Agent retries submission on failure (up to 5 attempts)
- [ ] Agent batches results (bulk_size from config)
- [ ] Agent throttles submissions (bulk_throttle_time)

**Submission Flow:**
```python
# After scan completes
results = execute_scan(job)  # Returns list of findings

# Batch results (default: 100 per batch)
batch_size = config['agent_script_executor']['bulk_size']
throttle_ms = config['agent_script_executor']['bulk_throttle_time_in_ms']

for batch in chunk_list(results, batch_size):
    # Submit batch
    response = POST(
        f"/api/v1/agents/jobs/{job.id}/results",
        json={"results": batch}
    )

    if response.status_code != 202:
        # Retry with exponential backoff
        retry_with_backoff(...)

    # Throttle between batches
    sleep(throttle_ms / 1000.0)

# Mark job as completed
POST(
    f"/api/v1/agents/jobs/{job.id}/complete",
    json={"status": "completed", "total_results": len(results)}
)
```

#### FR-AGENT-007: Configuration Updates
**Priority:** P1 (Should Have)
**User Story:** As an agent, I want to apply configuration updates without restarting so I can adapt to new settings.

**Acceptance Criteria:**
- [ ] Agent checks config_updated flag in heartbeat response
- [ ] Agent fetches new config via GET /api/v1/agents/config
- [ ] Agent validates configuration before applying
- [ ] Agent applies config changes (heartbeat interval, retry, etc.)
- [ ] Agent logs configuration updates

**Update Flow:**
```
1. POST /api/v1/agents/heartbeat
   └─ Response: {config_updated: true}

2. GET /api/v1/agents/config
   └─ Response: {
        heartbeat: {interval_in_seconds: 300},  // Changed from 600
        retry: {...}
      }

3. Validate config:
   - interval_in_seconds > 60
   - retry.attempts > 0

4. Apply config:
   - Update next_heartbeat_time
   - Update retry_policy
   - Update scheduler

5. Log change:
   [2025-01-15 10:30:45] INFO: Configuration updated
   [2025-01-15 10:30:45] INFO: Heartbeat interval: 600s → 300s
```

#### FR-AGENT-008: Auto-Update (Optional)
**Priority:** P2 (Nice to Have)
**User Story:** As an agent, I want to auto-update my binary so I get the latest features and fixes.

**Acceptance Criteria:**
- [ ] Agent checks for updates via GET /api/v1/agents/updates
- [ ] Agent downloads new binary if update_to_latest=true
- [ ] Agent verifies binary signature
- [ ] Agent replaces itself and restarts
- [ ] Agent reports new version on next heartbeat

**Update Flow:**
```
# Triggered by config: update_to_latest=true

1. GET /api/v1/agents/updates
   └─ Response: {
        update_available: true,
        latest_version: "1.1.0",
        download_url: "https://controller.example.com/api/v1/agents/updates/1.1.0/download",
        checksum: "sha256:abcd1234..."
      }

2. Download new binary:
   wget https://controller.example.com/api/v1/agents/updates/1.1.0/download \
     -O /tmp/gvm-agent-1.1.0

3. Verify checksum:
   echo "abcd1234... /tmp/gvm-agent-1.1.0" | sha256sum -c

4. Replace binary:
   sudo mv /tmp/gvm-agent-1.1.0 /usr/bin/gvm-agent
   sudo chmod +x /usr/bin/gvm-agent

5. Restart service:
   sudo systemctl restart gvm-agent

6. New agent reports version:
   POST /api/v1/agents/heartbeat
   {agent_version: "1.1.0"}
```

### 6.3 gvmd Integration

#### FR-GVMD-001: Agent Installer Distribution
**Priority:** P1 (Should Have)
**User Story:** As an admin, I want to download agent installers from gvmd so I can deploy agents to endpoints.

**Acceptance Criteria:**
- [ ] Agent installers visible in gvmd via GET_AGENT_INSTALLERS GMP command
- [ ] Installers available for Windows (.exe), Linux (.deb, .rpm), macOS (.pkg)
- [ ] Installers downloadable via GET_AGENT_INSTALLER_FILE GMP command
- [ ] Installers pre-configured with controller URL and auth token
- [ ] Installers include NVT feed (optional, for offline deployment)

**GMP Commands:**
```xml
<!-- List agent installers -->
<get_agent_installers/>

<!-- Response -->
<get_agent_installers_response>
  <agent_installer id="installer-uuid-1">
    <name>GVM Agent for Windows x64</name>
    <version>1.0.0</version>
    <file_extension>.exe</file_extension>
    <operating_system>Windows</operating_system>
    <architecture>amd64</architecture>
  </agent_installer>
  <agent_installer id="installer-uuid-2">
    <name>GVM Agent for Ubuntu/Debian</name>
    <version>1.0.0</version>
    <file_extension>.deb</file_extension>
    <operating_system>Linux</operating_system>
    <architecture>amd64</architecture>
  </agent_installer>
</get_agent_installers_response>

<!-- Download installer -->
<get_agent_installer_file agent_installer_id="installer-uuid-1"/>

<!-- Response: base64-encoded binary -->
<get_agent_installer_file_response>
  <agent_installer_file>
    <content encoding="base64">TVqQAAMAAAAEAAAA...</content>
  </agent_installer_file>
</get_agent_installer_file_response>
```

#### FR-GVMD-002: Agent Management in GSA
**Priority:** P0 (Must Have)
**User Story:** As an admin, I want to view and manage agents in the GSA web interface.

**Acceptance Criteria:**
- [ ] GSA displays "Agents" page (new menu item)
- [ ] Shows agent list with status (online/offline)
- [ ] Shows agent details (hostname, OS, IPs, version)
- [ ] Allows authorizing/deauthorizing agents
- [ ] Allows deleting agents
- [ ] Shows agent groups
- [ ] Allows assigning agents to groups

**UI Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Greenbone Security Assistant                                │
├─────────────────────────────────────────────────────────────┤
│ Scans | Assets | SecInfo | [Agents] | Administration        │
└─────────────────────────────────────────────────────────────┘

Agents
──────────────────────────────────────────────────────────────

Filter: [All Agents ▼]  [●●● Create Group]

┌────────────────────────────────────────────────────────────┐
│ Hostname              Status   OS          Last Seen   Auth │
├────────────────────────────────────────────────────────────┤
│ ● server1.example.com Online   Ubuntu 22.04  2 min ago  [✓]│
│ ● server2.example.com Online   Windows 2019  3 min ago  [✓]│
│ ○ server3.example.com Offline  CentOS 8      2 days ago [✓]│
│ ● laptop1.corp.local  Online   macOS 13      1 min ago  [✗]│
└────────────────────────────────────────────────────────────┘

Selected: 1 agent
[Authorize] [Delete] [Add to Group]
```

#### FR-GVMD-003: Agent Groups
**Priority:** P1 (Should Have)
**User Story:** As an admin, I want to organize agents into groups so I can scan logical collections of endpoints.

**Acceptance Criteria:**
- [ ] Agents can be assigned to multiple groups
- [ ] Groups can be used as targets in scan tasks
- [ ] Creating task with agent group target sends scan to all agents in group
- [ ] Groups support dynamic membership (e.g., "All Windows Servers")

**GMP Commands:**
```xml
<!-- Create agent group -->
<create_agent_group>
  <name>Remote Workers</name>
  <comment>All laptops for remote employees</comment>
</create_agent_group>

<!-- Add agents to group -->
<modify_agent_group agent_group_id="group-uuid">
  <add_agents>
    <agent id="agent-uuid-1"/>
    <agent id="agent-uuid-2"/>
  </add_agents>
</modify_agent_group>

<!-- Create task targeting agent group -->
<create_task>
  <name>Scan Remote Workers</name>
  <config id="config-uuid"/>
  <scanner id="agent-controller-scanner-uuid"/>
  <agent_group id="group-uuid"/>  <!-- Instead of target -->
</create_task>
```

---

## 7. Technical Requirements

### 7.1 Agent Controller Service

#### TR-AC-001: Technology Stack
**Priority:** P0 (Must Have)

**Backend:**
- Language: Go (performance, concurrency, cross-platform)
- Web Framework: Gin or Echo (HTTP routing)
- Database: PostgreSQL (relational data, ACID guarantees)
- Cache: Redis (job queue, session storage)
- Message Queue: RabbitMQ or Redis Streams (job distribution)

**Why Go:**
- Excellent concurrency (handle 10,000+ agents)
- Fast HTTP server performance
- Easy cross-compilation (Linux, Windows, macOS)
- Strong standard library (HTTP, TLS, JSON)

**Alternative:** Python with FastAPI (easier development, slower performance)

#### TR-AC-002: Database Schema
**Priority:** P0 (Must Have)

**Tables:**

```sql
-- Agents
CREATE TABLE agents (
  agent_id UUID PRIMARY KEY,
  hostname TEXT NOT NULL,
  connection_status TEXT NOT NULL,  -- 'online', 'offline', 'inactive'
  last_heartbeat TIMESTAMP NOT NULL,
  ip_addresses JSONB,               -- Array of IP addresses
  operating_system TEXT,
  architecture TEXT,
  agent_version TEXT,
  authorized BOOLEAN DEFAULT false,
  update_to_latest BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Scans
CREATE TABLE scans (
  scan_id UUID PRIMARY KEY,
  status TEXT NOT NULL,              -- 'queued', 'running', 'completed', 'failed'
  progress INTEGER DEFAULT 0,        -- 0-100
  vts JSONB NOT NULL,                -- Array of VT configurations
  scanner_preferences JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  completed_at TIMESTAMP
);

-- Jobs (one per agent per scan)
CREATE TABLE jobs (
  job_id UUID PRIMARY KEY,
  scan_id UUID NOT NULL REFERENCES scans(scan_id),
  agent_id UUID NOT NULL REFERENCES agents(agent_id),
  status TEXT NOT NULL,              -- 'queued', 'assigned', 'running', 'completed', 'failed'
  assigned_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  config JSONB NOT NULL,             -- Full job configuration
  UNIQUE(scan_id, agent_id)
);

-- Results
CREATE TABLE results (
  result_id UUID PRIMARY KEY,
  scan_id UUID NOT NULL REFERENCES scans(scan_id),
  agent_id UUID NOT NULL REFERENCES agents(agent_id),
  job_id UUID NOT NULL REFERENCES jobs(job_id),
  nvt_oid TEXT NOT NULL,
  host TEXT NOT NULL,
  port TEXT,
  severity DECIMAL,
  threat TEXT,
  description TEXT,
  qod INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Configuration
CREATE TABLE agent_config (
  config_id SERIAL PRIMARY KEY,
  config_data JSONB NOT NULL,       -- Global agent configuration
  version INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  is_current BOOLEAN DEFAULT true
);

-- Indexes
CREATE INDEX idx_agents_status ON agents(connection_status);
CREATE INDEX idx_agents_heartbeat ON agents(last_heartbeat);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_jobs_agent ON jobs(agent_id, status);
CREATE INDEX idx_jobs_scan ON jobs(scan_id);
CREATE INDEX idx_results_scan ON results(scan_id);
```

#### TR-AC-003: Job Queue Implementation
**Priority:** P0 (Must Have)

**Requirements:**
- FIFO queue per agent (preserve scan order)
- Job priority support (high/normal/low)
- Job expiration (stale jobs auto-canceled after 24h)
- Job retry on failure (up to 3 retries)

**Implementation:**

```go
// Using Redis Streams
package jobqueue

type JobQueue struct {
    redis *redis.Client
}

// Enqueue job for specific agent
func (jq *JobQueue) Enqueue(agentID string, job *Job) error {
    queueKey := fmt.Sprintf("agent:jobs:%s", agentID)

    jobData, _ := json.Marshal(job)

    _, err := jq.redis.XAdd(&redis.XAddArgs{
        Stream: queueKey,
        MaxLen: 1000,  // Limit queue size
        Values: map[string]interface{}{
            "job_id":   job.ID,
            "job_data": jobData,
            "priority": job.Priority,
        },
    }).Result()

    return err
}

// Dequeue jobs for agent
func (jq *JobQueue) Dequeue(agentID string, limit int) ([]*Job, error) {
    queueKey := fmt.Sprintf("agent:jobs:%s", agentID)

    entries, err := jq.redis.XRead(&redis.XReadArgs{
        Streams: []string{queueKey, "0"},
        Count:   int64(limit),
        Block:   0,
    }).Result()

    // Parse entries into Job structs
    jobs := make([]*Job, 0)
    for _, msg := range entries[0].Messages {
        var job Job
        json.Unmarshal([]byte(msg.Values["job_data"].(string)), &job)
        jobs = append(jobs, &job)
    }

    return jobs, nil
}
```

#### TR-AC-004: Heartbeat Monitoring
**Priority:** P0 (Must Have)

**Requirements:**
- Background job checks agent heartbeats every minute
- Marks agents as "offline" if heartbeat > interval * (1 + miss_until_inactive)
- Marks agents as "inactive" if offline > 24 hours
- Triggers alerts for critical agents going offline

**Implementation:**

```go
// Background job runs every 60 seconds
func (ac *AgentController) MonitorHeartbeats() {
    ticker := time.NewTicker(60 * time.Second)

    for range ticker.C {
        agents, _ := ac.db.GetAllAgents()

        for _, agent := range agents {
            // Get heartbeat config (default: 600s, miss_until_inactive: 1)
            interval := 600  // seconds
            threshold := interval * (1 + 1)  // 1200 seconds = 20 minutes

            timeSinceHeartbeat := time.Since(agent.LastHeartbeat).Seconds()

            if timeSinceHeartbeat > float64(threshold) {
                if agent.ConnectionStatus != "offline" {
                    ac.db.UpdateAgentStatus(agent.ID, "offline")
                    ac.logger.Warn("Agent went offline", "agent_id", agent.ID)
                }

                // If offline for 24 hours, mark inactive
                if timeSinceHeartbeat > 86400 {
                    ac.db.UpdateAgentStatus(agent.ID, "inactive")
                }
            }
        }
    }
}
```

### 7.2 Host-Based Agent

#### TR-AGENT-001: Technology Stack
**Priority:** P0 (Must Have)

**Core:**
- Language: C (for NASL interpreter, reuse OpenVAS scanner code)
- HTTP Client: libcurl (HTTPS, TLS, authentication)
- JSON Parser: cJSON or jansson
- Database: SQLite (NVT cache, local state)
- Logging: syslog (Linux) / Event Log (Windows)

**Why C:**
- OpenVAS scanner is written in C (code reuse)
- NASL interpreter requires C (performance, low-level access)
- Cross-platform (Linux, Windows, macOS)

**Alternative:** Go wrapper around C NASL interpreter (hybrid approach)

#### TR-AGENT-002: NASL Interpreter
**Priority:** P0 (Must Have)

**Source:** Fork OpenVAS Scanner
- Repository: https://github.com/greenbone/openvas-scanner
- License: GPL v2+ (compatible with open-source distribution)
- Components to reuse:
  - NASL interpreter (`nasl/nasl.c`, `nasl/nasl_builtin_*.c`)
  - Network functions (`misc/network.c`, `misc/plugutils.c`)
  - Knowledge Base (`kb/kb_redis.c` or in-memory alternative)
  - Result formatting

**Modifications Required:**
- Remove OSP protocol server
- Add HTTP client for polling
- Add job queue processor
- Add result submission logic

#### TR-AGENT-003: NVT Feed Management
**Priority:** P0 (Must Have)

**Feed Source:**
- Primary: Greenbone Community Feed (rsync://feed.community.greenbone.net/nvt-feed)
- Alternative: Agent Controller caching (HTTP download)
- Fallback: Bundled feed with installer (offline deployments)

**Sync Mechanism:**
```bash
#!/bin/bash
# /opt/gvm-agent/bin/sync-feed.sh

FEED_URL="rsync://feed.community.greenbone.net/nvt-feed"
FEED_DIR="/opt/gvm-agent/plugins"
GPG_KEY="/opt/gvm-agent/keys/greenbone-feed.asc"

# Sync feed
rsync -av --delete "$FEED_URL" "$FEED_DIR/"

# Verify signature
gpg --homedir /opt/gvm-agent/.gnupg \
    --verify "$FEED_DIR/sha256sums.asc" "$FEED_DIR/sha256sums"

if [ $? -ne 0 ]; then
    echo "ERROR: Feed signature verification failed"
    exit 1
fi

# Rebuild NVT cache
/opt/gvm-agent/bin/gvm-agent --update-nvt-cache

echo "Feed sync completed"
```

**NVT Cache Database:**
```sql
-- /var/lib/gvm-agent/nvt_cache.db

CREATE TABLE nvts (
  oid TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  family TEXT NOT NULL,
  filename TEXT NOT NULL,
  version TEXT,
  cvss_base DECIMAL,
  last_modification INTEGER,
  dependencies TEXT,  -- Comma-separated OIDs
  INDEX idx_family (family)
);

-- Example entries
INSERT INTO nvts VALUES (
  '1.3.6.1.4.1.25623.1.0.10662',
  'SSH Server Detection',
  'Service detection',
  '/opt/gvm-agent/plugins/2024/gb_ssh_detect.nasl',
  '2024-01-15',
  0.0,
  1705318800,
  ''
);
```

#### TR-AGENT-004: Configuration File
**Priority:** P0 (Must Have)

**Location:**
- Linux: `/etc/gvm-agent/agent.conf`
- Windows: `C:\Program Files\GVM Agent\agent.conf`
- macOS: `/Library/Application Support/GVM Agent/agent.conf`

**Format:** TOML or INI

```toml
[agent]
agent_id = "550e8400-e29b-41d4-a716-446655440001"  # Auto-generated on first run
hostname = "server1.example.com"

[controller]
url = "https://agent-controller.example.com"
auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
# Alternative: certificate-based auth
# client_cert = "/etc/gvm-agent/client.crt"
# client_key = "/etc/gvm-agent/client.key"
# ca_cert = "/etc/gvm-agent/ca.crt"

[heartbeat]
interval_in_seconds = 600
miss_until_inactive = 1

[retry]
attempts = 5
delay_in_seconds = 60
max_jitter_in_seconds = 30

[scanning]
max_concurrent_scans = 1
scan_timeout_seconds = 3600
max_vt_timeout_seconds = 300

[nvt_feed]
source = "rsync://feed.community.greenbone.net/nvt-feed"
sync_schedule = "0 2 * * *"  # 2 AM daily (cron format)
feed_dir = "/opt/gvm-agent/plugins"
verify_gpg = true

[logging]
level = "info"  # debug, info, warn, error
output = "syslog"  # syslog, file, stdout
# log_file = "/var/log/gvm-agent/agent.log"
```

#### TR-AGENT-005: Platform-Specific Requirements
**Priority:** P0 (Must Have)

**Linux:**
- Packaging: .deb (Debian/Ubuntu), .rpm (RHEL/CentOS)
- Service: systemd unit file
- Permissions: Runs as root (required for local scanning)
- Dependencies: libcurl, libssh, libpcap, openssl

**Systemd Unit:**
```ini
# /etc/systemd/system/gvm-agent.service

[Unit]
Description=GVM Agent for Vulnerability Scanning
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/gvm-agent --daemon
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10s
User=root
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=gvm-agent

[Install]
WantedBy=multi-user.target
```

**Windows:**
- Packaging: .exe installer (NSIS or WiX)
- Service: Windows Service
- Permissions: Runs as SYSTEM
- Dependencies: Bundled (statically linked)

**Windows Service Registration:**
```cmd
REM Install service
sc create "GVMAgent" binPath= "C:\Program Files\GVM Agent\gvm-agent.exe --service" start= auto

REM Start service
sc start "GVMAgent"
```

**macOS:**
- Packaging: .pkg installer
- Service: launchd plist
- Permissions: Runs as root
- Dependencies: Bundled or via Homebrew

**LaunchDaemon:**
```xml
<!-- /Library/LaunchDaemons/com.greenbone.gvm-agent.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.greenbone.gvm-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/gvm-agent</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/gvm-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/gvm-agent.error.log</string>
</dict>
</plist>
```

---

## 8. API Specifications

### 8.1 API #1: HTTP Scanner API (gvmd → Agent Controller)

**Base Path:** `/{scan_prefix}/scans` (default: `/scans`)
**Authentication:** Optional API key (configurable)
**Protocol:** HTTP/HTTPS

**Endpoints:**

| Method | Endpoint | Purpose | Status Codes |
|--------|----------|---------|--------------|
| POST | `/scans` | Create scan | 201 Created, 400 Bad Request |
| POST | `/scans/{id}` | Start/stop scan | 200 OK, 404 Not Found |
| GET | `/scans/{id}/status` | Get scan status | 200 OK, 404 Not Found |
| GET | `/scans/{id}/results` | Get results | 200 OK, 404 Not Found |
| DELETE | `/scans/{id}` | Delete scan | 204 No Content, 404 Not Found |
| GET | `/scans/preferences` | Get scan options | 200 OK |
| GET | `/health/alive` | Health check | 200 OK |
| GET | `/health/ready` | Readiness check | 200 OK, 503 Service Unavailable |
| GET | `/health/started` | Startup check | 200 OK |

**Detailed in Section 6.1 (Functional Requirements)**

### 8.2 API #2: Agent Controller Admin API (gvmd → Agent Controller)

**Base Path:** `/api/v1/admin/`
**Authentication:** **Required** - API key in `X-API-Key` header
**Protocol:** HTTPS only

**Endpoints:**

| Method | Endpoint | Purpose | Status Codes |
|--------|----------|---------|--------------|
| GET | `/api/v1/admin/agents` | List agents | 200 OK, 401 Unauthorized |
| PATCH | `/api/v1/admin/agents` | Update agents | 200 OK, 400 Bad Request, 422 Unprocessable Entity |
| POST | `/api/v1/admin/agents/delete` | Delete agents | 200 OK, 400 Bad Request |
| GET | `/api/v1/admin/scan-agent-config` | Get global config | 200 OK |
| PUT | `/api/v1/admin/scan-agent-config` | Update global config | 200 OK, 400 Bad Request |
| GET | `/api/v1/admin/agents/updates` | List updates | 200 OK |

**Detailed in Section 6.1 (Functional Requirements)**

### 8.3 API #3: Agent-Facing API (Agents → Agent Controller)

**Base Path:** `/api/v1/agents/`
**Authentication:** **Required** - Bearer token or mTLS
**Protocol:** HTTPS only

**Endpoints:**

| Method | Endpoint | Purpose | Status Codes |
|--------|----------|---------|--------------|
| POST | `/api/v1/agents/heartbeat` | Send heartbeat | 200 OK, 401 Unauthorized |
| GET | `/api/v1/agents/config` | Get agent config | 200 OK |
| GET | `/api/v1/agents/jobs` | Poll for jobs | 200 OK |
| POST | `/api/v1/agents/jobs/{id}/results` | Submit results | 202 Accepted, 400 Bad Request |
| POST | `/api/v1/agents/jobs/{id}/complete` | Mark job complete | 200 OK, 404 Not Found |
| GET | `/api/v1/agents/updates` | Check for updates | 200 OK |
| GET | `/api/v1/agents/updates/{version}/download` | Download update | 200 OK, 404 Not Found |
| GET | `/api/v1/agents/feed` | Download NVT feed | 200 OK |

**Detailed in Section 6.1 (Functional Requirements)**

### 8.4 Error Response Format

**Standard Error Response:**
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid agent_id format",
    "details": [
      {
        "field": "agent_id",
        "issue": "Must be a valid UUID"
      }
    ],
    "request_id": "req-550e8400-..."
  }
}
```

**Error Codes:**
- `INVALID_REQUEST` - Malformed request (400)
- `UNAUTHORIZED` - Missing or invalid auth (401)
- `FORBIDDEN` - Insufficient permissions (403)
- `NOT_FOUND` - Resource doesn't exist (404)
- `CONFLICT` - Resource already exists (409)
- `VALIDATION_ERROR` - Request validation failed (422)
- `INTERNAL_ERROR` - Server error (500)
- `SERVICE_UNAVAILABLE` - Service down (503)

---

## 9. Security Requirements

### 9.1 Authentication and Authorization

#### SR-AUTH-001: Agent Controller API Authentication
**Priority:** P0 (Must Have)

**Requirements:**
- All Admin API endpoints require API key authentication
- All Agent API endpoints require agent authentication (token or mTLS)
- Scanner API authentication optional (for gvmd compatibility)
- API keys stored hashed in database (bcrypt or Argon2)
- Agent tokens include expiration (JWT with exp claim)

**Implementation:**
```go
// Middleware for API key auth
func APIKeyAuth(c *gin.Context) {
    apiKey := c.GetHeader("X-API-Key")

    if apiKey == "" {
        c.JSON(401, gin.H{"error": "Missing API key"})
        c.Abort()
        return
    }

    // Verify API key
    valid, err := verifyAPIKey(apiKey)
    if !valid || err != nil {
        c.JSON(401, gin.H{"error": "Invalid API key"})
        c.Abort()
        return
    }

    c.Next()
}

// Middleware for agent token auth
func AgentAuth(c *gin.Context) {
    authHeader := c.GetHeader("Authorization")

    if !strings.HasPrefix(authHeader, "Bearer ") {
        c.JSON(401, gin.H{"error": "Missing bearer token"})
        c.Abort()
        return
    }

    token := strings.TrimPrefix(authHeader, "Bearer ")

    // Verify JWT token
    claims, err := verifyJWT(token)
    if err != nil {
        c.JSON(401, gin.H{"error": "Invalid token"})
        c.Abort()
        return
    }

    // Add agent_id to context
    c.Set("agent_id", claims.AgentID)
    c.Next()
}
```

#### SR-AUTH-002: Agent Authorization
**Priority:** P0 (Must Have)

**Requirements:**
- Agents must be explicitly authorized by admin before accepting jobs
- Unauthorized agents can heartbeat but cannot fetch jobs
- Authorization stored in `agents.authorized` boolean field
- Admin can authorize/deauthorize via GSA or GMP commands

**Flow:**
```
1. Agent installs and starts
2. Agent sends first heartbeat
   └─ Agent Controller creates agent record with authorized=false
3. Admin sees new agent in GSA
4. Admin clicks "Authorize" button
   └─ gvmd: PATCH /api/v1/admin/agents {authorized: true}
5. Next agent heartbeat returns authorized=true
6. Agent begins polling for jobs
```

### 9.2 Transport Security

#### SR-TLS-001: Mandatory TLS 1.3
**Priority:** P0 (Must Have)

**Requirements:**
- Agent Controller enforces TLS 1.3 (or TLS 1.2 minimum)
- Agents connect via HTTPS only (no HTTP support)
- Agent Controller presents valid TLS certificate
- Certificate from trusted CA or self-signed with pinning
- Disable weak ciphers (no SSLv3, TLS 1.0, TLS 1.1)

**Configuration:**
```go
// TLS config for Agent Controller server
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    PreferServerCipherSuites: true,
    CipherSuites: []uint16{
        tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
        tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
    },
}

server := &http.Server{
    Addr:      ":8443",
    Handler:   router,
    TLSConfig: tlsConfig,
}

server.ListenAndServeTLS("server.crt", "server.key")
```

#### SR-TLS-002: Mutual TLS (mTLS) Support
**Priority:** P1 (Should Have)

**Requirements:**
- Agent Controller supports mTLS for agent authentication
- Agents present client certificate during TLS handshake
- Agent Controller validates client certificate against CA
- Agent ID extracted from certificate Subject or SAN

**Configuration:**
```go
// mTLS config
caCert, _ := ioutil.ReadFile("ca.crt")
caCertPool := x509.NewCertPool()
caCertPool.AppendCertsFromPEM(caCert)

tlsConfig := &tls.Config{
    ClientAuth: tls.RequireAndVerifyClientCert,
    ClientCAs:  caCertPool,
}
```

### 9.3 Data Security

#### SR-DATA-001: Encryption at Rest
**Priority:** P1 (Should Have)

**Requirements:**
- Database connections encrypted (PostgreSQL SSL mode)
- Sensitive fields encrypted (credentials, API keys)
- Encryption key management (external KMS or local keyring)
- NVT feed stored unencrypted (signed, not secret)

**Encryption:**
```go
// Encrypt sensitive fields
func encryptCredential(plaintext, key string) (string, error) {
    aesKey := sha256.Sum256([]byte(key))
    block, _ := aes.NewCipher(aesKey[:])
    gcm, _ := cipher.NewGCM(block)
    nonce := make([]byte, gcm.NonceSize())
    rand.Read(nonce)
    ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
    return base64.StdEncoding.EncodeToString(ciphertext), nil
}
```

#### SR-DATA-002: Secrets Management
**Priority:** P0 (Must Have)

**Requirements:**
- No secrets in configuration files (use environment variables)
- API keys generated with cryptographically secure RNG
- Passwords hashed with bcrypt (cost >= 12)
- Agent tokens signed with HMAC-SHA256 or RS256

**Best Practices:**
```bash
# Environment variables for secrets
export AGENT_CONTROLLER_DB_PASSWORD="..."
export AGENT_CONTROLLER_API_KEY="..."
export AGENT_CONTROLLER_JWT_SECRET="..."

# Or use secrets management service
# - HashiCorp Vault
# - AWS Secrets Manager
# - Azure Key Vault
```

### 9.4 Input Validation

#### SR-VALID-001: Request Validation
**Priority:** P0 (Must Have)

**Requirements:**
- Validate all API inputs (JSON schema validation)
- Sanitize string inputs (prevent injection)
- Validate UUIDs format
- Validate IP addresses format
- Validate port ranges (1-65535)
- Validate OIDs format (dotted decimal notation)
- Reject requests exceeding size limits (e.g., 10MB)

**Validation Example:**
```go
// UUID validation
func validateUUID(uuid string) bool {
    pattern := `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
    matched, _ := regexp.MatchString(pattern, uuid)
    return matched
}

// OID validation
func validateOID(oid string) bool {
    pattern := `^[0-9]+(\.[0-9]+)+$`
    matched, _ := regexp.MatchString(pattern, oid)
    return matched
}

// Request size limit middleware
func RequestSizeLimit(maxSize int64) gin.HandlerFunc {
    return func(c *gin.Context) {
        c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxSize)
        c.Next()
    }
}
```

### 9.5 Audit Logging

#### SR-AUDIT-001: Security Event Logging
**Priority:** P1 (Should Have)

**Requirements:**
- Log all authentication attempts (success/failure)
- Log all authorization failures
- Log admin actions (agent authorization, deletion, config changes)
- Log agent registration/deregistration
- Log scan creation/completion
- Include timestamp, user/agent ID, action, outcome
- Store logs securely (append-only, tamper-evident)

**Log Format (JSON):**
```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "event": "agent.authorized",
  "actor": {
    "type": "admin",
    "user_id": "admin@example.com"
  },
  "target": {
    "type": "agent",
    "agent_id": "550e8400-..."
  },
  "action": "authorize_agent",
  "outcome": "success",
  "details": {
    "agent_hostname": "server1.example.com",
    "previous_status": "unauthorized"
  }
}
```

---

## 10. Performance Requirements

### 10.1 Scalability

#### PR-SCALE-001: Agent Capacity
**Priority:** P0 (Must Have)

**Requirements:**
- Single Agent Controller instance supports 1,000 concurrent agents (MVP)
- Single Agent Controller instance supports 10,000 concurrent agents (Phase 2)
- Horizontal scaling supports 100,000+ agents (Phase 3)

**Load Profile:**
- 10,000 agents × 1 heartbeat/10 min = ~17 heartbeats/second
- 1,000 concurrent scans × 100 results/scan = 100,000 results stored
- Peak load: 100 scans starting simultaneously

**Benchmarks:**
```bash
# Test heartbeat throughput
ab -n 10000 -c 100 -T application/json \
   -H "Authorization: Bearer TOKEN" \
   https://controller.example.com/api/v1/agents/heartbeat

# Expected: >1000 req/sec
```

#### PR-SCALE-002: Database Performance
**Priority:** P0 (Must Have)

**Requirements:**
- Heartbeat updates: < 10ms latency (p95)
- Job query: < 50ms latency (p95)
- Result insertion: < 100ms latency (p95)
- Scan status query: < 100ms latency (p95)

**Optimization:**
- Database connection pooling (100 connections)
- Indexed queries (see database schema)
- Batch inserts for results (bulk_size: 100)
- Read replicas for query scaling

#### PR-SCALE-003: Message Queue Throughput
**Priority:** P0 (Must Have)

**Requirements:**
- Job enqueue: 1,000 jobs/second
- Job dequeue: 10,000 jobs/second
- Queue latency: < 100ms (p99)

**Implementation:**
- Redis Streams (high throughput)
- Or RabbitMQ with quorum queues
- Partitioned queues (one per agent or shard)

### 10.2 Availability

#### PR-AVAIL-001: Uptime SLA
**Priority:** P1 (Should Have)

**Requirements:**
- Agent Controller availability: 99.9% (43 minutes downtime/month)
- Planned maintenance windows: 4 hours/month
- Automatic failover: < 30 seconds (Phase 3)

**Monitoring:**
- Health checks every 10 seconds
- Alert on 3 consecutive failures
- Prometheus + Grafana for metrics

#### PR-AVAIL-002: Graceful Degradation
**Priority:** P1 (Should Have)

**Requirements:**
- Agents continue scanning if controller temporarily unavailable
- Agents buffer results if controller unreachable (up to 1000 results)
- Agents retry heartbeat with exponential backoff
- Agents resume normal operation when controller returns

**Agent Behavior:**
```
Controller goes down:
  1. Agent detects heartbeat failure
  2. Agent retries with backoff (60s, 120s, 240s, ...)
  3. Agent continues executing current scan
  4. Agent buffers completed results locally
  5. After 5 failed attempts, agent waits for next interval
  6. Agent continues polling

Controller returns:
  1. Next heartbeat succeeds
  2. Agent submits buffered results
  3. Agent resumes normal polling
```

### 10.3 Agent Performance

#### PR-AGENT-001: Resource Usage
**Priority:** P0 (Must Have)

**Requirements:**
- Idle CPU: < 1% (agent waiting for jobs)
- Scanning CPU: < 50% average (agent executing scan)
- Memory: < 200 MB idle, < 1 GB scanning
- Disk: < 500 MB (agent binary + NVT feed cached elsewhere)
- Network: < 100 KB/s average (heartbeat + results)

**Monitoring:**
```bash
# Linux
top -p $(pgrep gvm-agent)
ps aux | grep gvm-agent
netstat -anp | grep gvm-agent

# Windows
Get-Process gvm-agent | Select CPU, WS
```

#### PR-AGENT-002: Scan Duration
**Priority:** P1 (Should Have)

**Requirements:**
- Full system scan (50,000 VTs): < 4 hours
- Quick scan (5,000 VTs): < 30 minutes
- Network discovery: < 5 minutes
- Configuration audit: < 15 minutes

**Variables:**
- VT count
- Target complexity (open ports, services)
- Credentials (authenticated scans slower)
- max_checks setting (concurrency)

---

## 11. Success Metrics

### 11.1 MVP Success Criteria (Phase 1)

**Functional Metrics:**
- [ ] 100+ agents successfully registered
- [ ] Scans created via gvmd execute on agents
- [ ] Results displayed in GSA reports
- [ ] 95% scan success rate (completed without errors)
- [ ] < 5% agent offline rate

**Performance Metrics:**
- [ ] Heartbeat latency: < 100ms (p95)
- [ ] Job queue latency: < 500ms (p95)
- [ ] Scan startup time: < 2 minutes
- [ ] Result submission latency: < 1 second (p95)

**Usability Metrics:**
- [ ] Agent deployment: < 15 minutes per agent
- [ ] Agent registration: < 5 minutes
- [ ] First scan results: < 20 minutes

### 11.2 Key Performance Indicators (KPIs)

**Operational KPIs:**
- Agent uptime: > 99% (agents online and heartbeating)
- Scan success rate: > 98% (scans complete successfully)
- Agent Controller uptime: > 99.9%
- Mean time to detection (MTTD): < 24 hours (vulnerabilities found)

**Business KPIs:**
- Agent deployment rate: 100 agents/week
- Total agents deployed: 1,000 (6 months), 10,000 (12 months)
- Scan frequency: 1 scan/agent/week average
- Vulnerability remediation rate: 50% within 30 days

**User Satisfaction KPIs:**
- Agent deployment satisfaction: > 4/5 stars
- Scan accuracy satisfaction: > 4/5 stars
- Performance satisfaction: > 4/5 stars

---

## 12. Implementation Phases

### 12.1 Phase 1: MVP (Q2 2025)

**Goal:** Prove core functionality with single OS

**Scope:**
- [ ] Agent Controller Service (basic implementation)
  - [ ] Scanner API (POST /scans, GET /scans/{id}/status, GET /scans/{id}/results)
  - [ ] Admin API (GET/PATCH /agents)
  - [ ] Agent API (POST /heartbeat, GET /jobs, POST /results)
  - [ ] PostgreSQL database
  - [ ] Redis job queue
- [ ] Host-Based Agent (Linux only)
  - [ ] NASL interpreter (OpenVAS fork)
  - [ ] NVT feed sync (rsync)
  - [ ] Heartbeat + polling logic
  - [ ] Local scanning
  - [ ] Result submission
- [ ] gvmd Integration
  - [ ] Agent Controller scanner registration
  - [ ] Agent management via GMP
  - [ ] Basic agent display in GSA

**Deliverables:**
- Agent Controller binary (Linux x64)
- Agent binary (Linux x64, .deb package)
- Installation guide
- API documentation
- Demo video

**Timeline:** 12 weeks
- Weeks 1-4: Agent Controller API development
- Weeks 5-8: Agent development (fork OpenVAS, add polling)
- Weeks 9-10: Integration testing
- Weeks 11-12: Documentation, demo

**Success Criteria:**
- 10 test agents deployed
- 5 successful scans executed
- Results visible in GSA

### 12.2 Phase 2: Multi-Platform (Q3 2025)

**Goal:** Production-ready with all OS support

**Scope:**
- [ ] Agent ports
  - [ ] Windows agent (.exe installer, Windows Service)
  - [ ] macOS agent (.pkg installer, launchd)
- [ ] Enhanced features
  - [ ] Agent groups
  - [ ] Agent auto-update
  - [ ] Configuration management (push config updates)
  - [ ] Scheduled scans (cron from config)
- [ ] Performance optimization
  - [ ] Database query optimization
  - [ ] Result batching
  - [ ] Connection pooling
- [ ] Security hardening
  - [ ] mTLS support
  - [ ] API key rotation
  - [ ] Audit logging

**Deliverables:**
- Agent binaries for Windows, macOS
- Agent group management UI
- Auto-update mechanism
- Performance benchmarks

**Timeline:** 10 weeks
- Weeks 1-4: Windows agent port
- Weeks 5-7: macOS agent port
- Weeks 8-9: Enhanced features
- Week 10: Testing, documentation

**Success Criteria:**
- 100+ agents across all platforms
- 50+ concurrent scans
- < 1% agent failure rate

### 12.3 Phase 3: Enterprise (Q4 2025)

**Goal:** Enterprise-grade scalability and features

**Scope:**
- [ ] High availability
  - [ ] Multiple Agent Controller instances (load balancing)
  - [ ] Database replication
  - [ ] Redis Cluster
  - [ ] Health checks and failover
- [ ] Advanced features
  - [ ] Compliance scanning (CIS, STIG)
  - [ ] Custom scan policies
  - [ ] Role-based access control (RBAC)
  - [ ] Multi-tenancy (separate organizations)
- [ ] Monitoring and observability
  - [ ] Prometheus metrics
  - [ ] Grafana dashboards
  - [ ] Distributed tracing (OpenTelemetry)
  - [ ] Alerting (PagerDuty, Slack)
- [ ] Documentation
  - [ ] Administrator guide
  - [ ] Deployment guide (Kubernetes, Docker Compose)
  - [ ] Troubleshooting guide
  - [ ] API reference (OpenAPI spec)

**Deliverables:**
- HA deployment architecture
- Kubernetes Helm charts
- Compliance scan templates
- Enterprise documentation

**Timeline:** 12 weeks
- Weeks 1-4: HA architecture implementation
- Weeks 5-8: Advanced features
- Weeks 9-10: Monitoring/observability
- Weeks 11-12: Documentation

**Success Criteria:**
- 10,000+ agents supported
- 99.99% uptime achieved
- Load test: 1,000 concurrent scans

---

## 13. Dependencies and Risks

### 13.1 External Dependencies

**Greenbone NVT Feed:**
- **Dependency:** OpenVAS vulnerability test feed
- **Source:** rsync://feed.community.greenbone.net/nvt-feed
- **License:** Mixed (GPL, proprietary Greenbone feed license)
- **Risk:** Feed access requires Greenbone Community Feed subscription (free) or Greenbone Enterprise Feed (paid)
- **Mitigation:** Bundle community feed with installer for offline deployments

**OpenVAS Scanner:**
- **Dependency:** NASL interpreter and scanning engine
- **Source:** https://github.com/greenbone/openvas-scanner
- **License:** GPL v2+
- **Risk:** Maintaining fork requires ongoing merge of upstream changes
- **Mitigation:** Minimize modifications, contribute changes upstream

**gvmd (Greenbone Vulnerability Manager):**
- **Dependency:** Integration requires gvmd 22.x or later with ENABLE_AGENTS=1
- **Risk:** gvmd API changes could break integration
- **Mitigation:** Test against multiple gvmd versions, use stable API

**Third-Party Libraries:**
- **Go:** Standard library, gin/echo (web framework), pq (PostgreSQL driver)
- **C:** libcurl, libssh, libpcap, openssl
- **Risk:** Security vulnerabilities in dependencies
- **Mitigation:** Automated dependency scanning (Dependabot, Snyk)

### 13.2 Technical Risks

#### Risk: NASL Interpreter Complexity
**Likelihood:** High
**Impact:** High
**Description:** NASL interpreter is complex (10,000+ lines of C code), difficult to maintain and debug.

**Mitigation:**
- Reuse OpenVAS scanner code (proven, battle-tested)
- Contribute improvements upstream
- Thorough testing with representative VTs
- Build regression test suite

#### Risk: Scalability Bottlenecks
**Likelihood:** Medium
**Impact:** High
**Description:** Agent Controller may not scale to 10,000+ agents without performance issues.

**Mitigation:**
- Load testing early and often (Phase 1)
- Profile and optimize hot paths
- Design for horizontal scaling from start
- Use proven technologies (PostgreSQL, Redis)

#### Risk: Security Vulnerabilities
**Likelihood:** Medium
**Impact:** Critical
**Description:** Agent Controller is high-value target (manages vulnerability data), agents run as root.

**Mitigation:**
- Security code review (OWASP Top 10)
- Penetration testing before production
- Bug bounty program
- Automated security scanning (Snyk, SonarQube)
- Principle of least privilege (agents drop privs when possible)

#### Risk: Cross-Platform Compatibility
**Likelihood:** Medium
**Impact:** Medium
**Description:** Agent must work across Windows, Linux, macOS with different filesystems, permissions, networking.

**Mitigation:**
- Test on all target platforms early
- Use platform abstraction layer
- Continuous integration with matrix builds
- Beta testing on real environments

### 13.3 Operational Risks

#### Risk: Agent Deployment Friction
**Likelihood:** High
**Impact:** Medium
**Description:** Users find agent deployment too complex, abandon product.

**Mitigation:**
- Simple installer (double-click .exe, dpkg -i .deb)
- Auto-registration (minimal manual steps)
- Ansible/Puppet/Chef modules for automation
- Cloud marketplace images (AWS AMI, Azure VM)

#### Risk: Performance Impact on Endpoints
**Likelihood:** Medium
**Impact:** High
**Description:** Agents consume too much CPU/memory, users disable them.

**Mitigation:**
- Resource limits (max 50% CPU)
- Scan throttling (configurable)
- Scheduled scanning (run during maintenance windows)
- Real-world performance testing
- User-configurable aggressiveness

#### Risk: NVT Feed Synchronization Issues
**Likelihood:** Medium
**Impact:** Medium
**Description:** Agents fail to sync feed due to network issues, wrong feed URL, disk space.

**Mitigation:**
- Retry logic for feed sync
- Fallback to Agent Controller-hosted feed
- Disk space checks before sync
- Feed sync status monitoring/alerting

### 13.4 Business Risks

#### Risk: Greenbone License Restrictions
**Likelihood:** Low
**Impact:** High
**Description:** Greenbone imposes license restrictions on agent-based scanning, requires paid feed.

**Mitigation:**
- Review Greenbone feed license terms
- Consider Greenbone Enterprise Feed (paid)
- Alternative: Use CVE data + custom tests
- Engage with Greenbone early (partnership?)

#### Risk: Market Competition
**Likelihood:** Medium
**Impact:** Medium
**Description:** Competing solutions (Qualys, Rapid7, Tenable agents) are more mature.

**Mitigation:**
- Differentiate: Open-source, self-hosted, privacy-focused
- Integrate with Greenbone ecosystem (GSA, gvmd)
- Target cost-conscious customers (SMBs, non-profits)
- Community-driven development

---

## 14. Open Questions

### 14.1 Architecture Questions

**Q1:** Should Agent Controller cache NVT feed for agents to download, or should agents sync directly from Greenbone feed?

**Options:**
- A) Agents sync from Greenbone feed directly (rsync)
- B) Agent Controller caches feed, agents download from controller
- C) Hybrid: Agents try Greenbone, fallback to controller

**Recommendation:** Option C (hybrid) - reduces Greenbone bandwidth, allows offline agents

**Q2:** Should agents buffer results locally if controller is unreachable?

**Options:**
- A) Yes, buffer up to 1000 results in SQLite
- B) No, fail fast and retry scan later
- C) Configurable (buffer_results: true/false)

**Recommendation:** Option A - improves reliability, allows scanning during controller outage

**Q3:** Should we support agent-to-agent communication for distributed scanning?

**Options:**
- A) Yes, agents can coordinate (e.g., leader election)
- B) No, all coordination via controller

**Recommendation:** Option B (MVP), revisit in Phase 3 if needed

### 14.2 Feature Questions

**Q4:** Should agents support scanning targets other than localhost?

**Options:**
- A) Yes, allow agents to scan arbitrary IPs (like OpenVAS)
- B) No, agents only scan localhost (endpoint scanning)
- C) Limited: Agents scan local subnet only

**Recommendation:** Option B (MVP), Option C (Phase 2) - maintains security, avoids network scanning complexity

**Q5:** Should we implement agent tags/labels for flexible grouping?

**Example:** `env=production`, `os=windows`, `location=us-east-1`

**Options:**
- A) Yes, tags stored in `agents` table as JSONB
- B) No, only support static groups
- C) Phase 2 feature

**Recommendation:** Option C - powerful feature, defer to Phase 2

**Q6:** Should Agent Controller support multiple gvmd instances (multi-tenancy)?

**Options:**
- A) Yes, tenant isolation via API keys
- B) No, one Agent Controller per gvmd
- C) Phase 3 feature

**Recommendation:** Option C - complex, enterprise feature

### 14.3 Technical Questions

**Q7:** What database should Agent Controller use?

**Options:**
- A) PostgreSQL (relational, proven)
- B) MongoDB (document store, flexible schema)
- C) SQLite (embedded, simple)

**Recommendation:** Option A - proven, ACID guarantees, relational data

**Q8:** How should agents authenticate with Agent Controller?

**Options:**
- A) JWT bearer tokens (simple, stateless)
- B) mTLS client certificates (more secure, complex)
- C) Both (configurable)

**Recommendation:** Option C - JWT for MVP, mTLS for enterprise

**Q9:** Should we build custom NASL interpreter or fork OpenVAS?

**Options:**
- A) Fork OpenVAS scanner (proven, complete)
- B) Build custom minimal interpreter (lighter)
- C) Hybrid: Minimal interpreter + OpenVAS fallback

**Recommendation:** Option A - proven, avoid reinventing wheel, faster time to market

### 14.4 Deployment Questions

**Q10:** How should agents be distributed?

**Options:**
- A) Via gvmd GMP commands (GET_AGENT_INSTALLER_FILE)
- B) Direct download from Agent Controller
- C) Public website / GitHub releases
- D) All of the above

**Recommendation:** Option D - maximum flexibility

**Q11:** Should Agent Controller be deployed as:

**Options:**
- A) Standalone service (separate from gvmd)
- B) gvmd plugin/extension
- C) Docker container
- D) Kubernetes Helm chart

**Recommendation:** Options A, C, D - standalone service with containerization for easy deployment

---

## Appendix A: Glossary

**Agent:** Host-based daemon deployed on endpoints that polls for scan jobs and executes vulnerability scans locally.

**Agent Controller:** HTTP REST service that bridges gvmd and agents, managing job distribution and result aggregation.

**Agent Group:** Logical collection of agents, used as scan target (e.g., "All Windows Servers").

**GMP (Greenbone Management Protocol):** XML-based protocol used by GSA and other clients to communicate with gvmd.

**GSA (Greenbone Security Assistant):** Web-based user interface for gvmd.

**gvmd (Greenbone Vulnerability Manager Daemon):** Core vulnerability management service that orchestrates scans, stores results, generates reports.

**Heartbeat:** Periodic message sent by agent to Agent Controller to maintain "online" status.

**NASL (Nessus Attack Scripting Language):** Scripting language used to write vulnerability tests (NVTs).

**NVT (Network Vulnerability Test):** Individual vulnerability test script (`.nasl` file) that checks for specific security issue.

**NVT Feed:** Collection of thousands of NVT scripts, maintained by Greenbone.

**OID (Object Identifier):** Unique identifier for each NVT (e.g., `1.3.6.1.4.1.25623.1.0.10662`).

**OpenVAS:** Open-source vulnerability scanner, core component of Greenbone Community Edition.

**OSP (Open Scanner Protocol):** Protocol used by gvmd to communicate with traditional scanners (replaced by HTTP for agents).

**Pull-Based Model:** Architecture where agents initiate connections to controller (vs. push-based where controller connects to agents).

**Scanner:** External service used by gvmd to execute vulnerability scans (OpenVAS, Agent Controller, etc.).

**VT (Vulnerability Test):** Synonym for NVT.

---

## Appendix B: References

**Code Evidence:**
- gvmd repository: https://github.com/greenbone/gvmd
- OpenVAS scanner: https://github.com/greenbone/openvas-scanner
- gvm-libs: https://github.com/greenbone/gvm-libs

**Documentation Created During Investigation:**
- `docs/AGENT_INSTALLER_INVESTIGATION.md` - Agent installer feature in gvmd
- `docs/SCANNER_CONCEPT.md` - What scanners are in gvmd architecture
- `docs/AGENT_BASED_SCANNING_EXPLAINED.md` - Agent architecture and pull model
- `docs/AGENT_CONTROLLER_API_EVIDENCE.md` - Proof of API functions in gvm-libs
- `docs/COMPLETE_AGENT_CONTROLLER_API_SPEC.md` - Complete three-API specification
- `docs/AGENT_FACING_API_ARCHITECTURE.md` - Agent polling model and lifecycle
- `docs/WHAT_AGENTS_NEED_TO_SCAN.md` - Requirements for agent scanning capability
- `docs/GVM_LIBS_ENDPOINT_INVESTIGATION.md` - Guide to finding endpoints in gvm-libs

**External References:**
- Greenbone Community Edition: https://www.greenbone.net/en/community-edition/
- Greenbone NVT Feed: https://community.greenbone.net/t/about-greenbone-community-feed-gcf/176
- OpenVAS Documentation: https://docs.greenbone.net/
- NASL Reference: https://docs.greenbone.net/GSM-Manual/gos-22.04/en/scanning.html#nasl

---

**End of Product Requirements Document**

**Document Control:**
- Version: 1.0
- Status: Draft
- Next Review: 2025-02-01
- Approval Required From: Engineering Lead, Product Owner, Security Lead

**Change Log:**
| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-01-15 | 1.0 | Claude + Investigation Team | Initial draft based on gvmd/gvm-libs investigation |
