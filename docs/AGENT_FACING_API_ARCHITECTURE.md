# Agent-Facing API Architecture: Complete System Design

## Executive Summary

**Critical Discovery:** The gvm-libs repository is a **CLIENT library collection** used by gvmd to communicate WITH external services. It does NOT contain the Agent Controller service itself.

This means there are actually **THREE distinct APIs** in the complete system:

1. **HTTP Scanner API** (`/scans`) - gvmd → Agent Controller (scan operations)
2. **Agent Controller Admin API** (`/api/v1/admin`) - gvmd → Agent Controller (agent management)
3. **Agent-Facing API** (`/api/v1/agents`) - **Agents → Agent Controller** (registration, heartbeat, job polling)

The third API is **NOT in gvm-libs** because agents don't use gvm-libs. The agent-facing endpoints must exist in the actual Agent Controller service implementation (separate repository).

---

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                            gvmd                                  │
│  (Uses gvm-libs client libraries to call Agent Controller)      │
└───────────┬─────────────────────────┬───────────────────────────┘
            │                         │
            │ HTTP Scanner API        │ Admin API
            │ POST /scans             │ PATCH /api/v1/admin/agents
            │ GET /scans/{id}/results │ GET /api/v1/admin/agents
            ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Controller Service                     │
│  (NOT in gvm-libs - separate service/repository)                │
│                                                                  │
│  Exposes 3 APIs:                                                │
│  1. HTTP Scanner API (for gvmd)                                 │
│  2. Admin API (for gvmd)                                        │
│  3. Agent API (for agents) ← INFERRED from gvm-libs structures  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Agent-Facing API
                            │ POST /api/v1/agents/heartbeat
                            │ GET /api/v1/agents/jobs
                            │ POST /api/v1/agents/results
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Deployed Agents                             │
│  (Poll for work, execute scans locally, report results)         │
│                                                                  │
│  - Windows agents                                               │
│  - Linux agents                                                 │
│  - macOS agents                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Three-API System Breakdown

### API #1: HTTP Scanner API (gvmd → Agent Controller)

**Purpose:** Scan lifecycle management
**Base Path:** `/{prefix}/scans`
**Authentication:** Optional
**Source:** gvm-libs/http_scanner/http_scanner.c

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /scans` | POST | Create scan |
| `GET /scans/{id}/status` | GET | Get scan status |
| `GET /scans/{id}/results` | GET | Get scan results |

### API #2: Agent Controller Admin API (gvmd → Agent Controller)

**Purpose:** Agent management (CRUD operations)
**Base Path:** `/api/v1/admin/`
**Authentication:** **Required** (API key)
**Source:** gvm-libs/agent_controller/agent_controller.c

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/v1/admin/agents` | GET | List agents |
| `PATCH /api/v1/admin/agents` | PATCH | Update agents |
| `POST /api/v1/admin/agents/delete` | POST | Delete agents |
| `GET /api/v1/admin/scan-agent-config` | GET | Get global agent config |
| `PUT /api/v1/admin/scan-agent-config` | PUT | Update global agent config |

### API #3: Agent-Facing API (Agents → Agent Controller)

**Purpose:** Agent registration, heartbeat, job polling, result reporting
**Base Path:** `/api/v1/agents/` (inferred)
**Authentication:** Agent authentication (token/certificate)
**Source:** **NOT in gvm-libs** (inferred from data structures)

| Endpoint | Method | Purpose | Evidence |
|----------|--------|---------|----------|
| `POST /api/v1/agents/heartbeat` | POST | Register & heartbeat | agent_controller.h:100-117 |
| `GET /api/v1/agents/config` | GET | Get agent config | agent_controller.h:66-117 |
| `GET /api/v1/agents/jobs` | GET | Poll for scan jobs | Pull model design |
| `POST /api/v1/agents/jobs/{id}/results` | POST | Submit scan results | Scan workflow |
| `GET /api/v1/agents/updates` | GET | Check for updates | agent_controller.c:1241 |

---

## Agent Pull-Based Polling Model

### Evidence from gvm-libs Structures

#### 1. Heartbeat Configuration (agent_controller.h:100-117)

```c
typedef struct agent_controller_heartbeat
{
  int interval_in_seconds;      // How often agent phones home (e.g., 600 = 10 min)
  int miss_until_inactive;      // Missed heartbeats before marked inactive (e.g., 1)
} agent_controller_heartbeat_t;
```

**What this tells us:**
- ✅ Agents **initiate** connection on a schedule (pull model)
- ✅ Default: Agents heartbeat every 10 minutes
- ✅ Agent Controller marks agents inactive if they miss 1 heartbeat
- ✅ Agents must maintain persistent connection awareness

#### 2. Agent Data Structure (agent_controller.c:338-405)

```c
typedef struct agent_data
{
  gchar *agentid;                           // Unique agent identifier
  gchar *hostname;                          // Agent hostname
  gchar *connection_status;                 // "active" | "inactive"
  time_t last_update;                       // Last time agent contacted controller
  time_t last_updater_heartbeat;           // Last heartbeat timestamp
  GPtrArray *ip_addresses;                  // Agent's IP addresses
  gchar *updater_version;                   // Agent updater version
  gchar *agent_version;                     // Agent binary version
  gchar *operating_system;                  // OS type and version
  gchar *architecture;                      // CPU architecture (amd64, arm64, etc.)
  gboolean update_to_latest;                // Flag: should agent auto-update?
  agent_controller_scan_agent_config_t config; // Agent configuration
} agent_data_t;
```

**What this tells us:**
- ✅ Agents send comprehensive system information during heartbeat
- ✅ Controller tracks `last_updater_heartbeat` - agents initiate contact
- ✅ Controller doesn't store agent callback URLs (pull model, not push)
- ✅ Configuration is distributed from controller to agents

#### 3. Retry & Bulk Processing (agent_controller.h:66-99)

```c
typedef struct agent_controller_retry
{
  int attempts;                  // Max retry attempts (e.g., 5)
  int delay_in_seconds;          // Base delay between retries (e.g., 60)
  int max_jitter_in_seconds;     // Random jitter (avoid thundering herd)
} agent_controller_retry_t;

typedef struct agent_controller_agent_script_executor
{
  int bulk_size;                          // Scripts per batch (e.g., 100)
  int bulk_throttle_time_in_ms;          // Sleep between batches (e.g., 1000)
  int indexer_dir_depth;                 // Max directory scan depth
  GPtrArray *scheduler_cron_time;        // Cron schedule (e.g., ["0 23 * * *"])
} agent_controller_agent_script_executor_t;
```

**What this tells us:**
- ✅ Agents have built-in retry logic for failed connections
- ✅ Random jitter prevents all agents from polling simultaneously
- ✅ Agents process work in batches (bulk_size)
- ✅ Agents can be scheduled for specific times (cron)
- ✅ Agents throttle their workload to avoid overwhelming endpoints

---

## Inferred Agent-Facing Endpoints

### 1. Agent Registration & Heartbeat

**Endpoint:** `POST /api/v1/agents/heartbeat`

**Purpose:** Agents register themselves and send periodic heartbeats to maintain "active" status.

**Agent Request:**
```http
POST /api/v1/agents/heartbeat HTTP/1.1
Host: agent-controller.example.com:443
Content-Type: application/json
Authorization: Bearer <agent-token>

{
  "agentid": "550e8400-e29b-41d4-a716-446655440001",
  "hostname": "server1.example.com",
  "connection_status": "active",
  "last_update": "2025-01-15T10:30:00Z",
  "last_updater_heartbeat": "2025-01-15T10:30:00Z",
  "ip_addresses": ["192.168.1.100", "10.0.0.50"],
  "updater_version": "1.0.0",
  "agent_version": "2.3.0",
  "operating_system": "Ubuntu 22.04 LTS",
  "architecture": "amd64",
  "update_to_latest": false
}
```

**Controller Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "accepted",
  "config_updated": false,
  "next_heartbeat_in_seconds": 600
}
```

**Evidence:**
- Field `last_updater_heartbeat` (agent_controller.c:342-343)
- Heartbeat interval configuration (agent_controller.h:100-117)
- Connection status field indicates agent-initiated status updates

**Frequency:** Default every 600 seconds (10 minutes)

---

### 2. Poll for Scan Jobs

**Endpoint:** `GET /api/v1/agents/jobs` or `GET /api/v1/agents/jobs?agentid={id}`

**Purpose:** Agents poll for work assigned to them by the Agent Controller.

**Agent Request:**
```http
GET /api/v1/agents/jobs?agentid=550e8400-e29b-41d4-a716-446655440001 HTTP/1.1
Host: agent-controller.example.com:443
Authorization: Bearer <agent-token>
```

**Controller Response (No Jobs):**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jobs": []
}
```

**Controller Response (Jobs Available):**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jobs": [
    {
      "job_id": "job-12345",
      "scan_id": "550e8400-e29b-41d4-a716-446655440000",
      "job_type": "vulnerability_scan",
      "priority": "high",
      "created_at": "2025-01-15T10:25:00Z",
      "config": {
        "scan_type": "full_and_fast",
        "target": "localhost",
        "port_range": "1-65535",
        "nvt_preferences": {...}
      }
    }
  ]
}
```

**Evidence:**
- Pull-based model (no agent callback URLs in data structures)
- Heartbeat interval suggests periodic polling
- Bulk processing configuration (agent_controller.h:82-99)
- Retry logic with jitter prevents thundering herd

**Polling Pattern:**
```
Agent starts
  ↓
Every 10 minutes (heartbeat interval):
  1. POST /api/v1/agents/heartbeat (stay alive)
  2. GET /api/v1/agents/jobs (check for work)
  3. If jobs available:
     - Download job details
     - Execute scan locally
     - POST results back
  4. Sleep with jitter (avoid simultaneous polling)
  5. Repeat
```

---

### 3. Get Agent Configuration

**Endpoint:** `GET /api/v1/agents/config`

**Purpose:** Agents fetch their configuration from the controller (retry policies, bulk settings, schedule).

**Agent Request:**
```http
GET /api/v1/agents/config HTTP/1.1
Host: agent-controller.example.com:443
Authorization: Bearer <agent-token>
X-Agent-ID: 550e8400-e29b-41d4-a716-446655440001
```

**Controller Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "retry": {
    "attempts": 5,
    "delay_in_seconds": 60,
    "max_jitter_in_seconds": 30
  },
  "agent_script_executor": {
    "bulk_size": 100,
    "bulk_throttle_time_in_ms": 1000,
    "indexer_dir_depth": 5,
    "scheduler_cron_time": ["0 23 * * *"]
  },
  "heartbeat": {
    "interval_in_seconds": 600,
    "miss_until_inactive": 1
  }
}
```

**Evidence:**
- Admin endpoint `/api/v1/admin/scan-agent-config` (agent_controller.c:1123)
- Full config structure in agent data (agent_controller.h:66-117)
- Agents need config to know retry policies and schedules

**When fetched:**
- On agent startup
- After controller signals `config_updated: true` in heartbeat response
- Periodically (e.g., every 24 hours)

---

### 4. Submit Scan Results

**Endpoint:** `POST /api/v1/agents/jobs/{job_id}/results`

**Purpose:** Agents submit vulnerability scan results to the controller.

**Agent Request:**
```http
POST /api/v1/agents/jobs/job-12345/results HTTP/1.1
Host: agent-controller.example.com:443
Content-Type: application/json
Authorization: Bearer <agent-token>

{
  "job_id": "job-12345",
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "agentid": "550e8400-e29b-41d4-a716-446655440001",
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
      "port": "22/tcp",
      "host": "192.168.1.100",
      "threat": "Medium",
      "description": "The remote SSH server is running an obsolete version.",
      "qod": 80
    }
  ],
  "total_results": 1
}
```

**Controller Response:**
```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "status": "accepted",
  "results_received": 1
}
```

**Evidence:**
- gvmd polls for results via `GET /scans/{id}/results` (http_scanner.c:670)
- Agent Controller must aggregate results from agents
- Results flow: Agent → Controller → gvmd (via Scanner API)

---

### 5. Check for Agent Updates

**Endpoint:** `GET /api/v1/agents/updates`

**Purpose:** Agents check if newer versions are available for auto-update.

**Agent Request:**
```http
GET /api/v1/agents/updates HTTP/1.1
Host: agent-controller.example.com:443
Authorization: Bearer <agent-token>
X-Agent-ID: 550e8400-e29b-41d4-a716-446655440001
X-Current-Version: 2.3.0
```

**Controller Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "update_available": true,
  "latest_version": "2.4.0",
  "download_url": "https://agent-controller.example.com/api/v1/agents/updates/2.4.0/download",
  "checksum": "sha256:abcd1234...",
  "release_notes": "Security fixes and performance improvements"
}
```

**Evidence:**
- Admin endpoint `/api/v1/admin/agents/updates` (agent_controller.c:1241)
- Field `update_to_latest` in agent data structure
- Fields `updater_version` and `agent_version` track versions

---

## Complete Agent Lifecycle

### 1. Agent Installation & Startup

```
1. User downloads agent installer (from gvmd via GMP)
   └─ GET_AGENT_INSTALLER_FILE command
   └─ gvmd returns .exe, .deb, or .pkg file

2. User installs agent on endpoint
   └─ Agent gets controller URL and auth token from config

3. Agent starts for first time
   └─ POST /api/v1/agents/heartbeat (initial registration)
   └─ GET /api/v1/agents/config (fetch configuration)
   └─ Agent status: "active" in controller
```

### 2. Normal Operation (Pull Loop)

```
Every heartbeat interval (default: 600 seconds):

┌─────────────────────────────────────────────────────┐
│  Agent Pull Loop (runs every 10 minutes)            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. POST /api/v1/agents/heartbeat                  │
│     └─ Send status, versions, IPs                  │
│     └─ Receive: config_updated flag                │
│                                                      │
│  2. IF config_updated == true:                      │
│     └─ GET /api/v1/agents/config                   │
│     └─ Update local configuration                  │
│                                                      │
│  3. GET /api/v1/agents/jobs                        │
│     └─ Check for assigned scan jobs                │
│                                                      │
│  4. IF jobs available:                              │
│     ├─ Download job details                         │
│     ├─ Execute vulnerability scan locally           │
│     │  └─ Full system access (local scanning)      │
│     ├─ Collect results                              │
│     └─ POST /api/v1/agents/jobs/{id}/results       │
│                                                      │
│  5. Sleep (interval + random jitter)                │
│     └─ Prevents thundering herd                     │
│                                                      │
│  6. Repeat                                           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 3. Auto-Update (If Enabled)

```
Periodically (e.g., daily at 23:00 via cron):

1. GET /api/v1/agents/updates
   └─ Check if newer version available

2. IF update_available && update_to_latest == true:
   ├─ Download new agent binary
   ├─ Verify checksum
   ├─ Stop current agent process
   ├─ Install new version
   └─ Restart agent

3. POST /api/v1/agents/heartbeat
   └─ New agent_version reported to controller
```

### 4. Agent Decommission

```
Admin action in gvmd:
1. DELETE_AGENT GMP command
   └─ gvmd → POST /api/v1/admin/agents/delete

Agent Controller:
2. Marks agent for deletion
3. Next time agent phones home:
   └─ Heartbeat response: {"status": "decommissioned"}

Agent:
4. Receives decommission signal
5. Cleans up local state
6. Stops heartbeat loop
7. Shuts down
```

---

## Configuration Management Flow

### Global Configuration (Set by Admin)

```
Admin (via gvmd):
  ↓
  PUT /api/v1/admin/scan-agent-config
  {
    "heartbeat": {"interval_in_seconds": 300},  // Change to 5 min
    "retry": {"attempts": 10}
  }
  ↓
Agent Controller: Updates global config
  ↓
Next agent heartbeat:
  Agent → POST /api/v1/agents/heartbeat
  Controller → {"config_updated": true}
  ↓
  Agent → GET /api/v1/agents/config
  Controller → Returns new config
  ↓
Agent: Applies new configuration (now heartbeats every 5 min)
```

### Per-Agent Configuration Override

```
Admin (via gvmd):
  ↓
  PATCH /api/v1/admin/agents
  {
    "agents": [
      {
        "agentid": "550e8400-...",
        "update_to_latest": true  // Enable auto-update for this agent
      }
    ]
  }
  ↓
Agent Controller: Updates agent-specific settings
  ↓
Next agent heartbeat:
  Agent → POST /api/v1/agents/heartbeat
  Controller → {"config_updated": true, "update_to_latest": true}
  ↓
Agent: Enables auto-update feature
```

---

## Retry & Resilience Patterns

### 1. Connection Retry with Exponential Backoff

```c
// From agent_controller.h:66-76
retry_config = {
  "attempts": 5,                    // Try up to 5 times
  "delay_in_seconds": 60,           // Start with 60s delay
  "max_jitter_in_seconds": 30       // Add 0-30s random jitter
};

// Agent implementation:
for (attempt = 0; attempt < 5; attempt++) {
  response = POST("/api/v1/agents/heartbeat");

  if (response.success) break;

  sleep_time = 60 * (2 ^ attempt);       // Exponential: 60, 120, 240, 480, 960
  jitter = random(0, 30);                 // Random 0-30 seconds
  sleep(sleep_time + jitter);
}
```

### 2. Bulk Processing with Throttling

```c
// From agent_controller.h:82-99
bulk_config = {
  "bulk_size": 100,                      // Process 100 items per batch
  "bulk_throttle_time_in_ms": 1000      // Sleep 1s between batches
};

// Agent implementation:
while (has_work) {
  batch = get_next_batch(bulk_size=100);
  process_batch(batch);
  sleep_ms(1000);  // Throttle to avoid overwhelming controller
}
```

### 3. Missed Heartbeat Detection

```c
// From agent_controller.h:100-117
heartbeat_config = {
  "interval_in_seconds": 600,       // Heartbeat every 10 minutes
  "miss_until_inactive": 1          // Mark inactive after 1 miss
};

// Agent Controller logic:
current_time = now();
last_heartbeat = agent.last_updater_heartbeat;
threshold = heartbeat_config.interval_in_seconds * (1 + heartbeat_config.miss_until_inactive);

if (current_time - last_heartbeat > threshold) {
  agent.connection_status = "inactive";
}
// If agent misses 1 heartbeat (600s), it's marked inactive after 1200s
```

---

## Security Considerations

### Agent Authentication

**Evidence:** Agents must authenticate to Agent-Facing API (not in gvm-libs, inferred).

**Likely Methods:**
1. **Bearer Token** - Agent receives token during installation
2. **mTLS** - Agent certificate issued by Agent Controller
3. **API Key** - Static key distributed with agent installer

**Authentication Flow:**
```
Agent Installation:
  └─ Agent configured with controller URL + auth credentials

First Heartbeat:
  Agent → POST /api/v1/agents/heartbeat
  Headers: Authorization: Bearer <token>
  Controller: Validates token, registers agent

Subsequent Requests:
  All agent requests include auth header
```

### Authorization Model

**gvmd → Agent Controller:**
- Admin API requires API key (agent_controller.c:807, 891, 978)
- Full CRUD access to all agents

**Agents → Agent Controller:**
- Agent can only access its own data (scoped by agent_id)
- No cross-agent access
- Read-only access to global config
- Write access only to own heartbeat/results

---

## Why Agent-Facing API Isn't in gvm-libs

### gvm-libs Purpose

gvm-libs is a **client library collection** for gvmd to use. It contains:

✅ HTTP client code to **call** Agent Controller admin endpoints
✅ HTTP client code to **call** HTTP Scanner endpoints
✅ Data structures for parsing responses
✅ Connection management (TLS, auth, retry)

### What gvm-libs Does NOT Contain

❌ Agent Controller service implementation
❌ Agent-facing endpoints (agents don't use gvm-libs)
❌ Agent binary implementation
❌ Job queue management
❌ Result aggregation logic

### Where Agent-Facing API Lives

The agent-facing API must exist in:

**Option 1:** Separate Agent Controller service repository
- Service exposes all 3 APIs (Scanner, Admin, Agent)
- Not open-sourced yet by Greenbone

**Option 2:** Bundled with Greenbone Enterprise Edition
- Commercial product, closed-source
- Full agent management capabilities

**Option 3:** Build your own open-source implementation
- Use gvm-libs structures as specification
- Implement agent-facing endpoints based on inferred design
- Integrate with gvmd via Scanner + Admin APIs

---

## Implementation Checklist for Building Agent Controller

If you're building an open-source Agent Controller with host-based agents:

### Agent Controller Service Must Implement:

#### API #1: HTTP Scanner API (for gvmd)
- [ ] `POST /scans` - Create scan, return scan_id
- [ ] `GET /scans/{id}/status` - Return scan status
- [ ] `GET /scans/{id}/results` - Return aggregated results from agents
- [ ] `DELETE /scans/{id}` - Cancel/delete scan
- [ ] Health checks (`/health/alive`, `/health/ready`, `/health/started`)

#### API #2: Admin API (for gvmd)
- [ ] `GET /api/v1/admin/agents` - List all registered agents
- [ ] `PATCH /api/v1/admin/agents` - Update agent properties
- [ ] `POST /api/v1/admin/agents/delete` - Delete agents
- [ ] `GET /api/v1/admin/scan-agent-config` - Get global config
- [ ] `PUT /api/v1/admin/scan-agent-config` - Update global config

#### API #3: Agent-Facing API (for agents)
- [ ] `POST /api/v1/agents/heartbeat` - Agent registration & heartbeat
- [ ] `GET /api/v1/agents/config` - Agent configuration retrieval
- [ ] `GET /api/v1/agents/jobs` - Job polling endpoint
- [ ] `POST /api/v1/agents/jobs/{id}/results` - Result submission
- [ ] `GET /api/v1/agents/updates` - Update check endpoint

### Agent Binary Must Implement:

#### Core Agent Functionality
- [ ] Heartbeat loop (default: every 600 seconds)
- [ ] Configuration management (fetch and apply)
- [ ] Job polling (check for work during heartbeat)
- [ ] Local vulnerability scanning (execute VTs)
- [ ] Result collection and submission
- [ ] Retry logic with exponential backoff and jitter
- [ ] Auto-update capability (optional)

#### Agent Configuration
- [ ] Controller URL (e.g., `https://agent-controller.example.com`)
- [ ] Authentication credentials (token/certificate)
- [ ] Agent ID (UUID)
- [ ] Heartbeat interval
- [ ] Retry policies
- [ ] Bulk processing settings

#### Local Scanning Engine
- [ ] VT (Vulnerability Test) execution framework
- [ ] System information collection (OS, architecture, IPs)
- [ ] Port scanning capabilities
- [ ] Service detection
- [ ] Result formatting (compatible with gvmd format)

---

## Summary: Three-API Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Complete System                          │
└─────────────────────────────────────────────────────────────────┘

API #1: HTTP Scanner API
  gvmd → Agent Controller
  Purpose: Scan operations (create, monitor, retrieve results)
  Source: gvm-libs/http_scanner/http_scanner.c

API #2: Agent Controller Admin API
  gvmd → Agent Controller
  Purpose: Agent management (CRUD operations)
  Source: gvm-libs/agent_controller/agent_controller.c

API #3: Agent-Facing API
  Agents → Agent Controller
  Purpose: Registration, heartbeat, job polling, result submission
  Source: NOT in gvm-libs (inferred from data structures)

Data Flow:
  gvmd creates scan → Agent Controller queues work →
  Agents poll for jobs → Agents execute locally →
  Agents submit results → Agent Controller aggregates →
  gvmd retrieves results
```

---

## Key Takeaways

1. **gvm-libs is CLIENT code only** - It's what gvmd uses to talk to Agent Controller

2. **Agent-facing API is separate** - Agents don't use gvm-libs; they call back to Agent Controller

3. **Pull-based model confirmed** - All evidence points to agents initiating connections:
   - Heartbeat intervals
   - No agent callback URLs stored
   - Retry logic with jitter
   - Poll-based job retrieval

4. **Three distinct APIs** - Scanner API (scans), Admin API (management), Agent API (polling)

5. **Configuration is distributed** - Controller pushes config updates via heartbeat responses

6. **Resilience built-in** - Retry logic, exponential backoff, jitter, bulk processing

7. **Agent Controller service exists elsewhere** - Not in gvmd, not in gvm-libs, separate implementation

---

## Next Steps for Investigation

To complete the picture, you would need to find or implement:

1. **Agent Controller Service** - The actual service that exposes all 3 APIs
2. **Agent Binary** - The host-based agent that polls for work
3. **Job Queue System** - How Agent Controller queues and distributes work
4. **Result Aggregation** - How Agent Controller collects results from multiple agents

**Note:** These components are not in the gvmd or gvm-libs repositories. They likely exist in:
- Greenbone Enterprise Edition (commercial, closed-source)
- Separate open-source project (if Greenbone has released one)
- To be built as custom implementation

---

## References

**gvm-libs Evidence:**
- `agent_controller/agent_controller.h` - Lines 66-117 (config structures)
- `agent_controller/agent_controller.c` - Lines 338-405 (agent data parsing)
- `agent_controller/agent_controller.c` - Lines 807, 891, 978, 1123, 1183, 1241 (admin endpoints)
- `http_scanner/http_scanner.c` - Lines 505, 670, 977 (scanner endpoints)

**gvmd Evidence:**
- `src/manage.c:7835-7945` - Scan creation flow
- `src/manage_agents.c:522-705` - Agent synchronization
- `src/manage_http_scanner.c:32-73` - HTTP scanner connection
