# Agent Controller Implementation Feasibility Analysis

## Executive Summary

**Conclusion: Building an open-source Agent Controller service is FEASIBLE**

Based on analysis of the gvmd source code and gvm-libs headers, we have sufficient information to implement a compatible Agent Controller service. This document outlines the evidence and rationale.

---

## Why It's Feasible

### 1. Complete API Contract Available

**Location:** `/usr/include/gvm/agent_controller/agent_controller.h`

This header file provides the complete client-side interface that gvmd uses to communicate with an Agent Controller service. It reveals:

#### Data Structures (Lines 39-166)

```c
// Connection configuration options
typedef enum {
  AGENT_CONTROLLER_CA_CERT,   // Path to CA certificate directory
  AGENT_CONTROLLER_CERT,      // Client certificate file
  AGENT_CONTROLLER_KEY,       // Client private key file
  AGENT_CONTROLLER_API_KEY,   // API key for authentication
  AGENT_CONTROLLER_PROTOCOL,  // "http" or "https"
  AGENT_CONTROLLER_HOST,      // Hostname or IP address
  AGENT_CONTROLLER_PORT       // Port number
} agent_controller_connector_opts_t;
```

#### Agent Data Structure (Lines 125-144)

```c
struct agent_controller_agent {
  gchar *agent_id;                    // Unique agent identifier
  gchar *hostname;                    // Hostname of the agent machine
  int authorized;                     // Authorization status (1/0)
  gchar *connection_status;           // "active" or "inactive"
  gchar **ip_addresses;               // List of IP addresses
  int ip_address_count;               // Number of IP addresses
  time_t last_update;                 // Timestamp of last update
  time_t last_updater_heartbeat;      // Timestamp of last heartbeat
  agent_controller_scan_agent_config_t config;  // Scan configuration
  gchar *updater_version;             // Updater version string
  gchar *agent_version;               // Agent version string
  gchar *operating_system;            // OS string
  gchar *architecture;                // Architecture (e.g., "amd64")
  int update_to_latest;               // Update flag (1/0)
};
```

#### Scan Agent Configuration (Lines 66-117)

```c
struct agent_controller_scan_agent_config {
  struct agent_controller_retry_cfg {
    int attempts;                     // Max retry attempts (e.g., 5)
    int delay_in_seconds;             // Base delay between retries (e.g., 60)
    int max_jitter_in_seconds;        // Random jitter (0..max)
  } agent_control.retry;

  struct agent_controller_script_exec_cfg {
    int bulk_size;                    // Scripts/tasks per batch
    int bulk_throttle_time_in_ms;     // Throttle between batches (ms)
    int indexer_dir_depth;            // Max directory scan depth
    GPtrArray *scheduler_cron_time;   // Cron expressions (5-field)
  } agent_script_executor;

  struct agent_controller_heartbeat_cfg {
    int interval_in_seconds;          // Heartbeat interval (e.g., 600)
    int miss_until_inactive;          // Missed beats before inactive
  } heartbeat;
};
```

#### Core API Functions (Lines 208-244)

```c
// Get list of agents from the controller
agent_controller_agent_list_t
agent_controller_get_agents(agent_controller_connector_t conn);

// Update multiple agents (authorization, config, etc.)
int agent_controller_update_agents(
  agent_controller_connector_t conn,
  agent_controller_agent_list_t agents,
  agent_controller_agent_update_t update,
  GPtrArray **errors
);

// Delete agents from the controller
int agent_controller_delete_agents(
  agent_controller_connector_t conn,
  agent_controller_agent_list_t agents
);

// Get scan agent configuration
agent_controller_scan_agent_config_t
agent_controller_get_scan_agent_config(agent_controller_connector_t conn);

// Update scan agent configuration
int agent_controller_update_scan_agent_config(
  agent_controller_connector_t conn,
  agent_controller_scan_agent_config_t cfg,
  GPtrArray **errors
);

// Get agents that have pending updates
agent_controller_agent_list_t
agent_controller_get_agents_with_updates(agent_controller_connector_t conn);
```

**Key Insight:** These function signatures directly map to HTTP REST endpoints the service must implement.

---

### 2. gvmd Integration Code Reveals Protocol Details

**File:** `src/manage_agent_common.c` (Lines 100-177)

#### Connector Builder (Lines 137-156)

```c
gvmd_agent_connector_t conn = g_malloc0(sizeof(struct gvmd_agent_connector));
conn->base = agent_controller_connector_new();

agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_HOST, host);
agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_PORT, &port);
agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_PROTOCOL, protocol);

if (ca_cert)
  agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_CA_CERT, ca_cert);
if (cert)
  agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_CERT, cert);
if (key)
  agent_controller_connector_builder(conn->base, AGENT_CONTROLLER_KEY, key);
```

**Reveals:**
- Service uses standard HTTP/HTTPS protocol
- Supports both API key and mTLS authentication
- Connection configured via scanner entries in gvmd database

---

**File:** `src/manage_agents.c`

#### Agent Synchronization Flow (Lines 138-298)

The `sync_agents_from_agent_controller()` function shows:
1. Call `agent_controller_get_agents()` to fetch all agents
2. Compare with local database
3. Insert new agents, update existing ones
4. Store agent data in `agents` table

#### Data Transformation (Lines 93-135)

Shows how agent controller config is copied and serialized, revealing:
- Configuration is likely JSON format
- Cron schedules stored as string array
- All numeric values are integers

---

**File:** `src/gmp_agents.c`

#### GMP Command Handlers

Shows how gvmd processes agent commands from GSA:

- `get_agents_run()` (Lines 100-340): Retrieves agents and formats XML response
- `handle_modify_agent()` (Lines 461-603): Updates agent authorization/config
- `handle_delete_agent()` (Lines 635-723): Deletes agents via controller

---

### 3. Authentication Methods Documented

**File:** `docs/integration-authentication.md` (Lines 1-79)

Specifies two supported authentication methods:

#### mTLS (Mutual TLS)
```
Client → Controller: Client certificate
Controller → Client: Validates certificate against CA
```

#### API Key
```
HTTP Header: X-API-KEY: <token>
```

**Note:** Both methods behave identically for agent controller connections.

---

### 4. Database Schema Available

**File:** `src/manage_sql_agents.c`

Shows the `agents` table structure and what fields gvmd expects to store:

```sql
CREATE TABLE agents (
  id SERIAL PRIMARY KEY,
  uuid TEXT UNIQUE,
  owner INTEGER REFERENCES users(id),
  name TEXT,
  comment TEXT,
  agent_id TEXT,           -- From agent controller
  hostname TEXT,
  authorized INTEGER,
  connection_status TEXT,  -- 'active' or 'inactive'
  scanner INTEGER REFERENCES scanners(id),
  creation_time INTEGER,
  modification_time INTEGER,
  last_update_agent_control INTEGER,
  schedule TEXT            -- JSON scan config
);
```

**File:** `src/manage_sql_agent_installers.c`

Shows agent installer data structure:
- Installer packages (name, version, platform)
- Download URLs or binary data
- Checksums/signatures

---

## Required REST API Endpoints

Based on the function calls in `agent_controller.h`, the service must implement:

### Core Endpoints

| HTTP Method | Endpoint | Function | Purpose |
|-------------|----------|----------|---------|
| GET | `/agents` | `agent_controller_get_agents()` | List all agents |
| GET | `/agents?updates=true` | `agent_controller_get_agents_with_updates()` | List agents with pending updates |
| PUT/PATCH | `/agents` | `agent_controller_update_agents()` | Update multiple agents (bulk) |
| DELETE | `/agents` | `agent_controller_delete_agents()` | Delete multiple agents (bulk) |
| GET | `/config` | `agent_controller_get_scan_agent_config()` | Get global scan config |
| PUT/PATCH | `/config` | `agent_controller_update_scan_agent_config()` | Update global scan config |
| GET | `/installers` | (implied) | List available agent installers |

### Request/Response Format

**Likely JSON** based on:
- `agent_controller_convert_scan_agent_config_string()` function (line 232-234 in agent_controller.h)
- `agent_controller_parse_scan_agent_config_string()` function (line 236-237)
- Modern REST API conventions

---

## Implementation Strategy

### Phase 1: Minimal Viable Service (2-4 hours)

**Goal:** Eliminate UI errors, make tabs functional

**Technology:** Python + Flask/FastAPI (rapid development)

**Features:**
- GET `/agents` - Return empty array initially
- GET `/config` - Return default configuration
- GET `/installers` - Return empty array
- Basic API key authentication
- In-memory data storage

**Result:** UI tabs work without errors, no actual agent management yet

---

### Phase 2: Basic Agent Management (4-8 hours)

**Goal:** Support manual agent registration and tracking

**Storage:** SQLite database

**Features:**
- POST `/agents/register` - Manual agent registration
- PUT `/agents/{id}` - Update agent authorization
- Heartbeat tracking (mark agents inactive after timeout)
- Persistent storage of agent metadata
- Agent IP address tracking

**Result:** Can manually add agents, authorize them, see them in UI

---

### Phase 3: Agent Installer Support (4-8 hours)

**Goal:** Provide downloadable agent packages

**Features:**
- GET `/installers` - List available installer packages
- GET `/installers/{id}/download` - Download installer binary
- Support for multiple platforms (Linux, Windows)
- Installer versioning

**Result:** Agent installer tab shows available downloads

---

### Phase 4: Full Agent Scanning Integration (8-16 hours)

**Goal:** Enable actual vulnerability scanning via agents

**Features:**
- Scan task distribution to agents
- Result collection from agents
- Script/VT synchronization
- Cron-based scheduling
- Bulk operations optimization

**Result:** End-to-end scanning via remote agents

---

## Minimal Service Example Structure

```
agent-controller/
├── main.py              # HTTP server (Flask/FastAPI)
├── models.py            # Data models (Agent, Config, Installer)
├── database.py          # SQLite/PostgreSQL persistence
├── api/
│   ├── agents.py        # Agent CRUD endpoints
│   ├── config.py        # Configuration endpoints
│   └── installers.py    # Installer endpoints
├── auth.py              # API key / mTLS authentication
├── requirements.txt     # Python dependencies
└── config.yaml          # Service configuration
```

**Estimated LOC:** 500-1000 lines for minimal viable implementation

---

## Evidence from Source Code Analysis

### File: `src/manage_agents.c`

**Line 139-177:** `sync_agents_from_agent_controller()` function
- Calls `agent_controller_get_agents(conn->base)`
- Expects `agent_controller_agent_list_t` with array of agents
- No complex protocol negotiation - simple request/response

**Line 387-450:** `modify_and_resync_agents()` function
- Creates `agent_controller_agent_update_t` structure
- Calls `agent_controller_update_agents()`
- Expects HTTP response with error array on failure

**Line 452-483:** `delete_and_resync_agents()` function
- Calls `agent_controller_delete_agents()`
- Simple success/failure response

### File: `src/gmp_agents.c`

**Line 472-473:** Configuration parsing
```c
agent_controller_scan_agent_config_t cfg =
  agent_controller_scan_agent_config_new();
```

Shows configuration is a structured object that can be serialized/deserialized.

**Line 207-208:** Config string parsing
```c
agent_controller_scan_agent_config_t cfg =
  agent_controller_parse_scan_agent_config_string(cfg_json);
```

Confirms JSON format for configuration exchange.

---

## Why This Will Work

### 1. **Well-Defined Interface**
The agent_controller.h header is a complete API contract. We know exactly what functions must be implemented.

### 2. **Simple HTTP Client**
The connector builder in `manage_agent_common.c` shows this is standard HTTP - no proprietary protocol.

### 3. **Standalone Service**
The agent controller is completely separate from gvmd - we can develop and test independently.

### 4. **Incremental Development**
Can start with stub endpoints that return empty data, then add features incrementally.

### 5. **Observable Behavior**
We can run gvmd with debug logging and observe the HTTP requests it makes to understand the protocol.

---

## Risks and Mitigations

### Risk 1: Undocumented Protocol Details
**Mitigation:** Use packet capture (tcpdump/Wireshark) on a test system to observe Enterprise Agent Controller traffic, OR reverse-engineer from gvm-libs HTTP client source code.

### Risk 2: Complex Agent Communication
**Mitigation:** Start with mock agents that report static data. Real agent protocol can be phase 2.

### Risk 3: Security Requirements
**Mitigation:** Implement API key auth first (simpler), add mTLS later as optional enhancement.

---

## Next Steps

1. **Extract gvm-libs agent_controller client source code**
   - Location: `/home/jake/decian-dev/gvm-libs/agent_controller/` (if available)
   - Reverse-engineer the exact HTTP requests made

2. **Create minimal Flask/FastAPI service**
   - Implement stub endpoints
   - Return properly formatted JSON responses

3. **Test with gvmd**
   - Create agent-controller scanner in database
   - Point to local service (localhost:3001)
   - Observe gvmd logs and HTTP traffic

4. **Iterate on protocol details**
   - Fix JSON format based on errors
   - Add required fields discovered through testing

---

## Conclusion

**Building an open-source Agent Controller is not only feasible but relatively straightforward.**

We have:
- ✅ Complete API specification (agent_controller.h)
- ✅ Database schema (manage_sql_agents.c)
- ✅ Integration code showing usage patterns
- ✅ Authentication documentation
- ✅ Clear separation of concerns (HTTP service)

**Estimated effort:**
- Minimal viable service: 4-8 hours
- Production-ready service: 40-80 hours

**Recommended approach:** Start with Python/Flask, transition to Go for performance if needed.

---

*Analysis Date: 2025-11-05*
*Analyst: Claude (Sonnet 4.5)*
*Based on: gvmd v26.6.0, gvm-libs v22.30.0*
