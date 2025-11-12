# Agent-Based Scanning with Scanner Types 7 & 9

## What Are "Agents"?

**An agent** is a **lightweight software program deployed on an endpoint** (workstation, laptop, server) that:

1. **Runs vulnerability scans locally** on that specific system
2. **Phones home** to an Agent Controller (doesn't require inbound network access)
3. **Reports scan results** back to the controller
4. **Receives scan instructions** from the controller

Think of it like this:

```
Traditional Network Scan (SCANNER_TYPE_OPENVAS):
┌──────────┐    Network    ┌──────────┐
│  gvmd    │ ────────────> │  Target  │
│          │   Probes      │  System  │
│ Scanner  │ <──────────── │          │
└──────────┘   Results     └──────────┘
     ↑
     └─ Scanner sends packets TO target


Agent-Based Scan (SCANNER_TYPE_AGENT_CONTROLLER):
┌──────────┐               ┌──────────┐
│  gvmd    │               │  Target  │
│          │               │  System  │
│          │               │          │
└────┬─────┘               └────┬─────┘
     │                          │
     │  ┌────────────────────┐  │
     └─>│ Agent Controller   │<─┘
        │    (Scanner)       │
        └────────────────────┘
             ↑
             └─ Agent phones home FROM target
```

---

## Agent Architecture

### Agent Components

```
┌─────────────────────────────────────────┐
│          Target System                  │
│  (Windows PC / Linux Server / Mac)      │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  Greenbone Agent Software         │ │
│  │                                   │ │
│  │  1. Local Scanner Engine          │ │ ← Runs vulnerability checks
│  │  2. Heartbeat Client              │ │ ← Periodic check-in
│  │  3. Config Receiver               │ │ ← Gets scan instructions
│  │  4. Result Uploader               │ │ ← Sends findings
│  │  5. Update Manager                │ │ ← Self-updates
│  └───────────────────────────────────┘ │
│              ↓ HTTPS                    │
└─────────────────────────────────────────┘
               ↓
         [Internet/VPN]
               ↓
┌─────────────────────────────────────────┐
│      Agent Controller Service           │
│    (HTTP REST API - Scanner Type 7)    │
│                                         │
│  - Tracks all deployed agents           │
│  - Manages agent configurations         │
│  - Receives agent heartbeats            │
│  - Orchestrates scans                   │
│  - Collects scan results                │
└─────────────────────────────────────────┘
               ↑
               │ HTTP/HTTPS
               ↓
┌─────────────────────────────────────────┐
│             gvmd                        │
│  (Vulnerability Management Daemon)      │
│                                         │
│  - Creates scan tasks                   │
│  - Selects agent groups                 │
│  - Triggers scans                       │
│  - Stores results in reports            │
└─────────────────────────────────────────┘
```

---

## Agent Data Structure

**Database Schema:** `src/manage_pg.c:2783-2803`

```sql
CREATE TABLE agents (
  id SERIAL PRIMARY KEY,
  uuid UUID NOT NULL UNIQUE,
  name TEXT NOT NULL,
  agent_id TEXT UNIQUE NOT NULL,           -- Unique agent identifier
  scanner INTEGER REFERENCES scanners,     -- Which Agent Controller manages this
  hostname TEXT,                           -- Agent's system hostname
  authorized INTEGER NOT NULL,             -- Is agent authorized to scan?
  connection_status TEXT,                  -- "connected", "disconnected", "inactive"
  last_update INTEGER,                     -- Last time agent synced
  last_updater_heartbeat INTEGER,          -- Last heartbeat timestamp
  config TEXT,                             -- JSON config for this agent
  owner INTEGER REFERENCES users,          -- Who owns this agent
  comment TEXT,
  creation_time INTEGER,
  modification_time INTEGER,
  updater_version TEXT,                    -- Agent updater software version
  agent_version TEXT,                      -- Agent scanning engine version
  operating_system TEXT,                   -- "Windows 11", "Ubuntu 22.04", etc.
  architecture TEXT,                       -- "x64", "arm64", etc.
  update_to_latest INTEGER                 -- Auto-update flag
);

-- Agents can have multiple IP addresses
CREATE TABLE agent_ip_addresses (
  agent_id TEXT REFERENCES agents (agent_id),
  ip_address TEXT NOT NULL
);
```

**Agent Data in Memory:** `src/manage_agents.h:51-76`

```c
struct agent_data {
  agent_t row_id;                           // Database row ID
  gchar *uuid;                              // Unique UUID
  gchar *name;                              // Human-readable name
  gchar *agent_id;                          // Agent's unique ID
  gchar *hostname;                          // System hostname
  int authorized;                           // Authorization status
  gchar *connection_status;                 // "connected", "disconnected", etc.
  agent_ip_data_list_t ip_addresses;       // List of IPs
  time_t last_update_agent_control;        // Last sync time
  time_t last_updater_heartbeat;           // Last heartbeat
  agent_controller_scan_agent_config_t config;  // Scan configuration
  gchar *comment;
  scanner_t scanner;                        // Which scanner (Agent Controller)
  gchar *updater_version;                   // Updater version
  gchar *agent_version;                     // Scanner version
  gchar *operating_system;                  // OS info
  gchar *architecture;                      // CPU arch
  int update_to_latest;                     // Auto-update enabled
};
```

---

## Agent Configuration

**Location:** `config` field in agents table (JSON format)

**Structure:** Based on `agent_controller_scan_agent_config_t`

```json
{
  "agent_control": {
    "retry": {
      "attempts": 3,
      "delay_in_seconds": 5,
      "max_jitter_in_seconds": 2
    }
  },
  "agent_script_executor": {
    "bulk_size": 100,
    "bulk_throttle_time_in_ms": 1000,
    "indexer_dir_depth": 3,
    "scheduler_cron_time": [
      "0 2 * * *",    // Daily at 2 AM
      "0 14 * * *"    // Daily at 2 PM
    ]
  },
  "heartbeat": {
    "interval_in_seconds": 300,      // Heartbeat every 5 minutes
    "miss_until_inactive": 3         // Inactive after 3 missed heartbeats
  }
}
```

**Purpose:**
- **Retry config:** How agent retries failed operations
- **Executor config:** How agent runs vulnerability checks
- **Heartbeat config:** How often agent checks in
- **Cron schedules:** When agent automatically runs scans

---

## How Agent-Based Scanning Works

### Phase 1: Agent Deployment

```
1. Build agent installer
   └─ Windows .exe, Linux .deb, macOS .pkg

2. Upload to gvmd feed directory
   └─ /var/lib/gvm/data-objects/gvmd/agent-installers/

3. User downloads from GSA frontend
   └─ get_agent_installer_file command

4. User installs on target systems
   └─ Agent software installed locally

5. Agent first boot
   ├─ Connects to Agent Controller (from config)
   ├─ Registers itself (sends system info)
   └─ Waits for authorization
```

### Phase 2: Agent Registration

**Agent → Agent Controller:**

```http
POST /agents/register HTTP/1.1
Host: agent-controller.example.com
Content-Type: application/json

{
  "hostname": "LAPTOP-WIN11",
  "operating_system": "Windows 11 Pro",
  "architecture": "x64",
  "ip_addresses": ["192.168.1.100", "10.0.0.50"],
  "agent_version": "1.3.0",
  "updater_version": "1.2.1"
}
```

**Agent Controller → gvmd:**

Agent Controller calls `agent_controller_get_agents()` which gvmd polls via:

```c
// src/manage_agents.c:sync_agents_from_agent_controller()
agent_controller_agent_list_t list =
    agent_controller_get_agents(connector);
```

gvmd then:
1. Receives new agent info
2. Creates entry in `agents` table
3. Sets `authorized = 0` (pending)
4. Notifies admin via GSA

### Phase 3: Agent Authorization

**Admin action in GSA:**

```
1. Views unauthorized agents
2. Reviews agent details (hostname, OS, IPs)
3. Clicks "Authorize Agent"
4. Optionally assigns to agent group
```

**gvmd → Agent Controller:**

```c
// src/manage_agents.c:modify_and_resync_agents()
agent_controller_update_agents(
  connector,
  agents,
  &agent_update,  // contains authorized=true
  &errors
);
```

**Translates to HTTP:**

```http
PUT /agents HTTP/1.1
Content-Type: application/json

{
  "agents": [
    {
      "agent_id": "abc-123-def",
      "authorized": true,
      "config": { ... }
    }
  ]
}
```

### Phase 4: Agent Heartbeat

**Continuous operation:**

```
Every 5 minutes (configurable):

Agent → Agent Controller:
  POST /heartbeat
  {
    "agent_id": "abc-123-def",
    "status": "idle",
    "last_scan": "2025-11-12T10:30:00Z"
  }

Agent Controller updates:
  - last_updater_heartbeat timestamp
  - connection_status ("connected")

If 3 heartbeats missed:
  - connection_status → "inactive"
```

### Phase 5: Scan Execution

**User creates task in GSA:**

```
1. Select scanner type: Agent Controller
2. Select agent group: "Finance Department PCs"
3. Select scan config: "Full and fast"
4. Schedule: Now
```

**gvmd orchestrates scan:**

**Step 1: Get agents from group**

```c
// src/manage.c:run_agent_control_task()
agent_group_t agent_group = task_agent_group(task);
agent_uuid_list_t agent_uuids = get_agent_uuids_from_group(agent_group);
```

**Step 2: Send scan request to Agent Controller**

```c
// src/manage.c:launch_agent_control_task()
payload = agent_controller_build_create_scan_payload(agent_list);

http_scanner_resp = http_scanner_post(
  connection,
  "/api/v1/scans",
  payload
);

scan_id = agent_controller_get_scan_id(http_scanner_resp->body);
```

**Translates to HTTP:**

```http
POST /api/v1/scans HTTP/1.1
Content-Type: application/json

{
  "scan_config": "...",
  "agents": [
    {
      "agent_id": "abc-123-def",
      "hostname": "LAPTOP-WIN11"
    },
    {
      "agent_id": "xyz-789-ghi",
      "hostname": "DESKTOP-SALES"
    }
  ]
}

Response:
{
  "scan_id": "scan-uuid-12345",
  "status": "queued"
}
```

**Step 3: Agent Controller → Agents**

Agent Controller pushes scan job to agents (or agents poll for it):

```
For each agent in scan:
  1. Agent Controller queues scan job
  2. Agent picks up job on next heartbeat/poll
  3. Agent runs local vulnerability scan
  4. Agent uploads results back to controller
```

**Step 4: gvmd polls for results**

```c
// src/manage.c:handle_agent_controller_scan()
connector = http_scanner_connect(scanner, scan_id);

// Poll every 5 seconds
while (progress < 100) {
  progress = http_scanner_get_scan_progress(connector);

  // Get incremental results
  http_scanner_parsed_results(connector, 0, -1, &results);

  // Store in gvmd report
  parse_http_scanner_report(task, report, results);
}

// Clean up
http_scanner_delete_scan(connector);
```

**Translates to HTTP:**

```http
GET /api/v1/scans/{scan_id}/status HTTP/1.1

Response:
{
  "scan_id": "scan-uuid-12345",
  "status": "running",
  "progress": 65,
  "start_time": "2025-11-12T14:00:00Z",
  "agents_completed": 1,
  "agents_total": 2
}

GET /api/v1/scans/{scan_id}/results?start=0 HTTP/1.1

Response:
{
  "results": [
    {
      "agent_id": "abc-123-def",
      "hostname": "LAPTOP-WIN11",
      "nvt_oid": "1.3.6.1.4.1.25623.1.0.12345",
      "name": "Windows Update Not Enabled",
      "severity": 7.5,
      "description": "...",
      "port": "general/tcp",
      "qod": 95
    }
  ]
}
```

### Phase 6: Result Storage

```c
// gvmd stores each result in reports table
for each result:
  - Create result_t
  - Associate with report
  - Index by host (agent hostname)
  - Calculate severity
  - Generate report summary
```

---

## Scanner Type 7 vs Type 9

### SCANNER_TYPE_AGENT_CONTROLLER (7)

**What it is:** Local/primary Agent Controller service

**Connection:**
```sql
INSERT INTO scanners VALUES (
  'Primary Agent Controller',
  'localhost',
  8080,
  7  -- SCANNER_TYPE_AGENT_CONTROLLER
);
```

**Use case:**
- Single datacenter/location
- All agents connect to one controller
- Controller runs on same network as gvmd

**Example deployment:**
```
┌─────────────────────────────────┐
│     Corporate Network           │
│                                 │
│  ┌───────┐    ┌──────────────┐ │
│  │ gvmd  │───>│    Agent     │ │
│  └───────┘    │  Controller  │ │
│               │   (Type 7)   │ │
│               └──────────────┘ │
│                      ↑          │
│         ┌────────────┼────────┐│
│         ↓            ↓         ↓│
│    ┌────────┐  ┌────────┐  ┌────────┐
│    │ Agent  │  │ Agent  │  │ Agent  │
│    │  PC1   │  │  PC2   │  │  PC3   │
│    └────────┘  └────────┘  └────────┘
└─────────────────────────────────┘
```

---

### SCANNER_TYPE_AGENT_CONTROLLER_SENSOR (9)

**What it is:** Remote Agent Controller sensor/relay

**Connection:**
```sql
INSERT INTO scanners VALUES (
  'EMEA Agent Controller',
  'agent-controller-emea.example.com',
  443,
  9  -- SCANNER_TYPE_AGENT_CONTROLLER_SENSOR
);
```

**Use case:**
- Multi-datacenter deployment
- Distributed agent management
- Regional controllers (AMER, EMEA, APAC)
- Each region has its own controller

**Example deployment:**
```
┌─────────────────────────────────────────────────┐
│            Global Corporate Network             │
│                                                 │
│  ┌────────────────────────┐                    │
│  │   Headquarters (US)    │                    │
│  │                        │                    │
│  │  ┌───────┐             │                    │
│  │  │ gvmd  │             │                    │
│  │  └───┬───┘             │                    │
│  └──────┼──────────────────┘                   │
│         │                                       │
│         ├──────────────┬──────────────┐        │
│         ↓              ↓              ↓        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  │   AMER      │ │   EMEA      │ │   APAC      │
│  │   Agent     │ │   Agent     │ │   Agent     │
│  │ Controller  │ │ Controller  │ │ Controller  │
│  │  (Type 9)   │ │  (Type 9)   │ │  (Type 9)   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
│         │                │                │      │
│    ┌────┴────┐      ┌───┴───┐       ┌───┴───┐  │
│    ↓         ↓      ↓       ↓       ↓       ↓  │
│ [US Agents] [Agents] [EU Agents] [Asia Agents]│
└─────────────────────────────────────────────────┘
```

**Benefits of Type 9:**
- **Reduced latency:** Agents in EU connect to EU controller
- **Better scalability:** Each controller handles fewer agents
- **Geographic distribution:** Compliance/data residency
- **Network segmentation:** Each region isolated
- **Failover:** If EMEA controller fails, AMER still works

---

## How Endpoint Scanning Works (Technical)

### 1. Agent Scans Locally

Unlike network scanning which sends packets:

```
Network Scanner (OPENVAS):
  └─ Sends TCP/UDP packets to target
  └─ Observes responses
  └─ Limited view (external perspective)

Agent (Local):
  └─ Reads files directly
  └─ Queries registry/system APIs
  └─ Checks running processes
  └─ Full system access (internal perspective)
```

**Example checks agent can do:**

```python
# Pseudo-code of what agent does locally

# 1. Check for missing patches
installed_patches = query_windows_update_history()
required_patches = get_cve_patch_list()
missing = required_patches - installed_patches

# 2. Check filesystem permissions
for file in sensitive_files:
    perms = get_file_permissions(file)
    if perms.world_readable:
        report_vulnerability("Sensitive file readable by all")

# 3. Check registry keys
reg_value = read_registry("HKLM\\System\\AutoLogon")
if reg_value.enabled:
    report_vulnerability("AutoLogon enabled - security risk")

# 4. Check running services
for service in get_running_services():
    if service.runs_as == "SYSTEM" and service.has_remote_access:
        report_vulnerability("Privileged service exposed")

# 5. Check local users
for user in get_local_users():
    if user.password_never_expires:
        report_vulnerability("User has non-expiring password")
```

### 2. Agent Advantage Over Network Scanning

| Check Type | Network Scanner | Agent |
|------------|----------------|-------|
| **Open ports** | ✅ Can detect | ✅ Can detect |
| **Service versions** | ⚠️ Banner grabbing | ✅ Exact version from binary |
| **Installed patches** | ❌ Cannot see | ✅ Full patch list |
| **File permissions** | ❌ Cannot see | ✅ Full filesystem access |
| **Registry settings** | ❌ Cannot see | ✅ Direct registry access |
| **Running processes** | ❌ Cannot see | ✅ Complete process list |
| **User accounts** | ⚠️ Limited info | ✅ Full user database |
| **Scheduled tasks** | ❌ Cannot see | ✅ Full task list |
| **Encryption status** | ❌ Cannot see | ✅ BitLocker/LUKS status |
| **Antivirus state** | ❌ Cannot see | ✅ AV status and updates |
| **Firewall rules** | ⚠️ Probe only | ✅ Complete ruleset |
| **Certificate store** | ❌ Cannot see | ✅ All installed certs |

### 3. Behind-Firewall Scanning

**Problem with network scanning:**

```
Internet              Firewall        Internal Network
─────────            ─────────        ─────────────────
                     │DENY ALL│
                     │ INBOUND│
                     │        │
┌────────┐          │        │       ┌──────────┐
│ gvmd   │─────X────│        │       │  Laptop  │
│Scanner │          │        │       │ (Remote) │
└────────┘          │        │       └──────────┘
                     │        │
    ❌ Blocked       └────────┘
```

**Solution with agents:**

```
Internet              Firewall        Internal Network
─────────            ─────────        ─────────────────
                     │ ALLOW  │
                     │OUTBOUND│
                     │        │
┌────────┐          │        │       ┌──────────┐
│ Agent  │<─────────│        │───────│  Laptop  │
│Control │          │        │       │  +Agent  │
└────────┘          │        │       └──────────┘
     ↑               │        │            │
     │               └────────┘            │
     └───────────────────────────────────┘
              ✅ Outbound only
```

**Agent phones home:**
- **Outbound HTTPS** (port 443) - Usually allowed
- **Agent initiates** connection - No inbound firewall rules needed
- **Periodic poll** - Agent asks "any scans for me?"
- **Push results** - Agent uploads findings

### 4. Mobile/Laptop Scanning

**Challenge:**
```
Day 1: Laptop at office    → IP: 10.0.1.50
Day 2: Laptop at home      → IP: 192.168.1.100
Day 3: Laptop at coffee    → IP: 172.16.5.200
```

**Network scanner fails:**
- Cannot reach laptop when roaming
- IP address constantly changing
- Laptop disconnected = unscanned

**Agent solution:**
```
Day 1: Agent connects from office
Day 2: Agent connects from home WiFi
Day 3: Agent connects from coffee shop WiFi

Agent always "calls home" regardless of location
```

---

## Agent Groups

**Purpose:** Organize agents for targeted scanning

**Database Schema:**

```sql
CREATE TABLE agent_groups (
  uuid TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  scanner INTEGER REFERENCES scanners,  -- Which controller
  owner INTEGER REFERENCES users,
  comment TEXT
);

CREATE TABLE agent_group_agents (
  group_id INTEGER REFERENCES agent_groups,
  agent_id INTEGER REFERENCES agents,
  PRIMARY KEY (group_id, agent_id)
);
```

**Example groups:**

```
Group: "Finance Department"
├─ Agent: FIN-WKS-001 (Desktop, Windows 11)
├─ Agent: FIN-WKS-002 (Desktop, Windows 11)
└─ Agent: FIN-LPT-001 (Laptop, Windows 11)

Group: "Linux Servers"
├─ Agent: WEB-SRV-01 (Ubuntu 22.04)
├─ Agent: DB-SRV-01 (Ubuntu 22.04)
└─ Agent: API-SRV-01 (RHEL 8)

Group: "Executive Laptops"
├─ Agent: CEO-MBP-01 (MacBook Pro, macOS 14)
├─ Agent: CFO-MBP-01 (MacBook Pro, macOS 14)
└─ Agent: CTO-LPT-01 (Laptop, Ubuntu 23.10)
```

**Scan targeting:**

```
Task 1: "Weekly Finance Scan"
  └─ Target: Agent Group "Finance Department"
  └─ Schedule: Every Monday 2 AM

Task 2: "Critical Server Scan"
  └─ Target: Agent Group "Linux Servers"
  └─ Schedule: Daily

Task 3: "Executive Security Check"
  └─ Target: Agent Group "Executive Laptops"
  └─ Schedule: Twice weekly
```

---

## Summary

### What Agents Are:
✅ **Software deployed on endpoints** (installed like any program)
✅ **Local vulnerability scanners** (run checks on their own system)
✅ **Pull-based** (agents connect to controller, not vice versa)
✅ **Self-updating** (can receive updates from controller)
✅ **Heartbeat-based** (phone home periodically)

### Scanner Type 7 (AGENT_CONTROLLER):
✅ **Local/primary controller** (one datacenter)
✅ **Manages deployed agents**
✅ **HTTP REST API**
✅ **Orchestrates scans across agents**
✅ **Collects and aggregates results**

### Scanner Type 9 (AGENT_CONTROLLER_SENSOR):
✅ **Remote/distributed controller** (multiple locations)
✅ **Same capabilities as Type 7**
✅ **Geographic distribution**
✅ **Better scalability**
✅ **Regional agent management**

### How Endpoint Scanning Works:
✅ **Agent scans locally** (direct filesystem/registry access)
✅ **More comprehensive** than network scanning
✅ **Works behind firewalls** (outbound only)
✅ **Handles mobile devices** (agents follow laptops)
✅ **Results uploaded** to controller
✅ **gvmd aggregates** all findings into reports

---

## Real-World Scenario

**Company Setup:**
- 500 Windows workstations
- 50 Linux servers
- 100 MacBooks (executives/developers)
- Offices in US, UK, Japan

**Traditional Approach (OPENVAS):**
- ❌ Laptops offline when remote
- ❌ Firewall blocks scans to some systems
- ❌ Limited visibility (external view only)
- ❌ Can't scan systems behind NAT/VPN

**Agent-Based Approach (AGENT_CONTROLLER):**
- ✅ Agents installed on all 650 systems
- ✅ 3 Agent Controllers (US, UK, Japan) - Type 9
- ✅ Agents connect regardless of location
- ✅ Full system visibility (internal checks)
- ✅ Laptops scanned even when traveling
- ✅ Periodic automatic scans via cron schedules
- ✅ Centralized management via gvmd

**Result:**
- **100% coverage** (all systems scanned)
- **More comprehensive** (local checks)
- **Always current** (mobile devices included)
- **Minimal network impact** (no port scanning traffic)
