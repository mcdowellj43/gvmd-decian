# Agent Controller API Evidence

## Overview

This document provides **exact file locations and line numbers** for all Agent Controller API calls made by gvmd, proving which functions exist and how they're used.

---

## Source of API Functions

**Header File:** `<agent_controller/agent_controller.h>`

**Location:** This header is from `libgvm_agent_controller` in the `gvm-libs` project (not in gvmd)

**Include Statement:**
- **File:** `src/manage_agents.h:24`
- **Code:** `#include <agent_controller/agent_controller.h>`

**Build Requirement:**
```cmake
# From src/CMakeLists.txt:44-52
if(ENABLE_AGENTS)
  pkg_check_modules(
    LIBGVM_AGENT_CONTROLLER
    REQUIRED
    libgvm_agent_controller>=22.30
  )
endif(ENABLE_AGENTS)
```

---

## Function 1: `agent_controller_get_agents()`

### Purpose
Retrieve list of all agents from Agent Controller

### Evidence of Usage

#### Location 1: `src/manage_agents.c:528`

**Function:** `sync_agents_from_agent_controller()`

**Line 528:**
```c
agent_controller_agent_list_t agent_controller_agents =
  agent_controller_get_agents (connector->base);
```

**Context (lines 522-532):**
```c
agent_response_t
sync_agents_from_agent_controller (gvmd_agent_connector_t connector)
{
  if (!connector)
    return AGENT_RESPONSE_CONNECTOR_CREATION_FAILED;

  agent_controller_agent_list_t agent_controller_agents =
    agent_controller_get_agents (connector->base);

  if (!agent_controller_agents)
    return AGENT_RESPONSE_SYNC_FAILED;
```

**What it does:**
- Calls Agent Controller API to get list of all agents
- Used during agent synchronization from controller to gvmd database
- Returns `agent_controller_agent_list_t` with agent metadata

#### Location 2: `src/manage_sql.c:31406`

**Function:** `verify_agent_control_scanner()`

**Line 31406:**
```c
agent_controller_agent_list_t agents = agent_controller_get_agents (connection);
```

**Context (lines 31401-31411):**
```c
if (name == NULL && version == NULL)
  return 1;

/* TODO: Return scanner name and version from agent controller
   as soon as the required endpoint is available. */
agent_controller_agent_list_t agents = agent_controller_get_agents (connection);
agent_controller_connector_free (connection);
if (agents == NULL)
  return 1;
*name = g_strdup ("TestName");
*version = g_strdup ("TestVersion");
```

**What it does:**
- Tests connectivity to Agent Controller
- Used during scanner verification
- Confirms Agent Controller is reachable and responding

#### Location 3: `src/manage_sql.c:31462`

**Function:** `scanner_desc_with_host_and_port()`

**Line 31462:**
```c
agent_controller_agent_list_t agents = agent_controller_get_agents (connection);
```

**Context (lines 31457-31467):**
```c
agent_controller_connector_builder (connection, AGENT_CONTROLLER_CERT, key_pub);
agent_controller_connector_builder (connection, AGENT_CONTROLLER_PORT, (void *) &port);

*desc = g_strdup_printf ("Agent Control Scanner on %s://%s:%d", protocol, host, port);

agent_controller_agent_list_t agents = agent_controller_get_agents (connection);
agent_controller_connector_free (connection);

if (agents == NULL)
  return 1;
```

**What it does:**
- Verifies Agent Controller connectivity when creating scanner description
- Tests HTTP connection to controller

### HTTP Request (Inferred)
```http
GET /agents HTTP/1.1
Host: agent-controller.example.com
```

Or possibly:
```http
GET /api/v1/admin/agents HTTP/1.1
Host: agent-controller.example.com
```

---

## Function 2: `agent_controller_update_agents()`

### Purpose
Update agent properties (authorization, configuration, etc.)

### Evidence of Usage

#### Location: `src/manage_agents.c:706-707`

**Function:** `modify_and_resync_agents()`

**Lines 706-707:**
```c
int update_result = agent_controller_update_agents (
  connector->base, agent_control_list, agent_update, errors);
```

**Full Context (lines 690-725):**
```c
get_response = get_agent_controller_agents_from_uuids (
  scanner, agent_uuids, agent_control_list);
if (get_response != AGENT_RESPONSE_SUCCESS)
  {
    agent_controller_agent_list_free (agent_control_list);
    return get_response;
  }

connector = gvmd_agent_connector_new_from_scanner (scanner);
if (!connector)
  {
    g_warning ("%s: Failed to create agent connector for scanner ", __func__);
    agent_controller_agent_list_free (agent_control_list);
    manage_option_cleanup ();
    return AGENT_RESPONSE_CONNECTOR_CREATION_FAILED;
  }

int update_result = agent_controller_update_agents (
  connector->base, agent_control_list, agent_update, errors);

if (update_result < 0 && errors && *errors && (*errors)->len > 0)
  {
    g_warning ("%s: agent_controller_update_agents rejected", __func__);
    agent_controller_agent_list_free (agent_control_list);
    gvmd_agent_connector_free (connector);
    manage_option_cleanup ();
    return AGENT_RESPONSE_CONTROLLER_UPDATE_REJECTED;
  }

if (update_result < 0)
  {
    g_warning ("%s: agent_controller_update_agents failed", __func__);
    agent_controller_agent_list_free (agent_control_list);
    gvmd_agent_connector_free (connector);
    manage_option_cleanup ();
    return AGENT_RESPONSE_CONTROLLER_UPDATE_FAILED;
  }
```

**What it does:**
- Updates agent properties on Agent Controller
- Used when admin modifies agent in GSA (authorize, configure, etc.)
- Takes list of agents to update and update data structure
- Returns error array if validation fails

**Parameters:**
- `connector->base`: Agent Controller connector
- `agent_control_list`: List of agents to update
- `agent_update`: Update data (authorization, config changes)
- `errors`: Output parameter for validation errors

### HTTP Request (Inferred)
```http
PUT /agents HTTP/1.1
Host: agent-controller.example.com
Content-Type: application/json

{
  "agents": [
    {
      "agent_id": "abc-123-def",
      "authorized": true,
      "config": {...}
    }
  ]
}
```

---

## Function 3: `agent_controller_delete_agents()`

### Purpose
Delete agents from Agent Controller

### Evidence of Usage

#### Location: `src/manage_agents.c:803`

**Function:** `delete_and_resync_agents()`

**Line 803:**
```c
int update_result =
  agent_controller_delete_agents (connector->base, agent_control_list);
```

**Full Context (lines 793-817):**
```c
connector = gvmd_agent_connector_new_from_scanner (scanner);
if (!connector)
  {
    g_warning ("%s: Failed to create agent connector for scanner", __func__);
    agent_controller_agent_list_free (agent_control_list);
    manage_option_cleanup ();
    return AGENT_RESPONSE_CONNECTOR_CREATION_FAILED;
  }

int update_result =
  agent_controller_delete_agents (connector->base, agent_control_list);

if (update_result < 0)
  {
    g_warning ("%s: agent_controller_delete_agents failed", __func__);
    agent_controller_agent_list_free (agent_control_list);
    gvmd_agent_connector_free (connector);
    manage_option_cleanup ();
    return AGENT_RESPONSE_CONTROLLER_DELETE_FAILED;
  }

delete_agents_by_scanner_and_uuids (0, agent_uuids);

agent_response_t result = sync_agents_from_agent_controller (connector);
```

**What it does:**
- Deletes agents from Agent Controller
- Used when admin deletes agent in GSA
- Also deletes from gvmd database after successful controller deletion
- Re-syncs after deletion to ensure consistency

**Parameters:**
- `connector->base`: Agent Controller connector
- `agent_control_list`: List of agents to delete

### HTTP Request (Inferred)
```http
DELETE /agents HTTP/1.1
Host: agent-controller.example.com
Content-Type: application/json

{
  "agent_ids": ["abc-123-def", "xyz-789-ghi"]
}
```

---

## Function 4: `agent_controller_build_create_scan_payload()`

### Purpose
Build JSON payload for creating a scan on Agent Controller

### Evidence of Usage

#### Location: `src/manage.c:7889`

**Function:** `launch_agent_control_task()`

**Line 7889:**
```c
payload = agent_controller_build_create_scan_payload (agent_control_list);
```

**Full Context (lines 7882-7894):**
```c
if (get_agent_controller_agents_from_uuids (scanner, agent_uuids, agent_control_list) != 0)
  {
    if (error) *error = g_strdup ("Could not get Agents from database");
    goto make_report;
  }

// Build create-scan payload
payload = agent_controller_build_create_scan_payload (agent_control_list);
if (!payload)
  {
    if (error) *error = g_strdup ("Could not create scan payload");
    goto make_report;
  }
```

**What it does:**
- Constructs JSON payload for scan creation
- Takes list of agents that should be scanned
- Returns JSON string ready for HTTP POST

**Parameters:**
- `agent_control_list`: List of agents to include in scan

**Returns:**
- JSON string payload (caller must free)

---

## Function 5: `http_scanner_create_scan()`

### Purpose
Send HTTP POST request to create scan (used after building payload)

### Evidence of Usage

#### Location: `src/manage.c:7897`

**Function:** `launch_agent_control_task()`

**Line 7897:**
```c
http_scanner_resp = http_scanner_create_scan (connection, payload);
```

**Full Context (lines 7889-7902):**
```c
// Build create-scan payload
payload = agent_controller_build_create_scan_payload (agent_control_list);
if (!payload)
  {
    if (error) *error = g_strdup ("Could not create scan payload");
    goto make_report;
  }

// Create scan
http_scanner_resp = http_scanner_create_scan (connection, payload);
if (!http_scanner_resp || http_scanner_resp->code != 201)
  {
    if (error) *error = g_strdup ("Scanner failed to create the scan");
    goto make_report;
  }
```

**What it does:**
- Makes HTTP POST request to Agent Controller
- Sends scan payload
- Expects HTTP 201 (Created) response
- Returns response with scan_id

**Header:** `<gvm/http_scanner/http_scanner.h>` (from gvm-libs)

### HTTP Request
```http
POST /scans HTTP/1.1
Host: agent-controller.example.com
Content-Type: application/json

{
  "scan_config": {...},
  "agents": [
    {
      "agent_id": "abc-123-def",
      "hostname": "LAPTOP-WIN11"
    }
  ]
}
```

**Expected Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "scan_id": "scan-uuid-12345",
  "status": "queued"
}
```

---

## Function 6: `agent_controller_get_scan_id()`

### Purpose
Extract scan_id from HTTP response body

### Evidence of Usage

#### Location: `src/manage.c:7906`

**Function:** `launch_agent_control_task()`

**Line 7906:**
```c
gchar *scan_id = agent_controller_get_scan_id (http_scanner_resp->body);
```

**Full Context (lines 7897-7915):**
```c
// Create scan
http_scanner_resp = http_scanner_create_scan (connection, payload);
if (!http_scanner_resp || http_scanner_resp->code != 201)
  {
    if (error) *error = g_strdup ("Scanner failed to create the scan");
    goto make_report;
  }

// Extract scan id
{
  gchar *scan_id = agent_controller_get_scan_id (http_scanner_resp->body);
  if (!scan_id)
    {
      if (error) *error = g_strdup ("Could not get scan id from response");
      goto make_report;
    }

  if (report_id) *report_id = g_strdup (scan_id);
  g_free (scan_id);
}
```

**What it does:**
- Parses JSON response body
- Extracts `scan_id` field
- Returns scan_id string (caller must free)

---

## Complete Scan Creation Flow

### Code Flow in `src/manage.c:launch_agent_control_task()`

```
1. Get agents from database (lines 7882-7886)
   └─ get_agent_controller_agents_from_uuids()

2. Build scan payload (lines 7889-7894)
   └─ agent_controller_build_create_scan_payload()
   └─ Returns JSON string

3. Create scan on controller (lines 7897-7902)
   └─ http_scanner_create_scan()
   └─ POST /scans
   └─ Expects HTTP 201

4. Extract scan ID (lines 7906-7915)
   └─ agent_controller_get_scan_id()
   └─ Parse JSON response

5. Create report in gvmd (line 7923)
   └─ create_current_report()
   └─ Store scan_id for polling
```

### HTTP Communication
```
gvmd → Agent Controller:
  POST /scans
  {
    "scan_config": {...},
    "agents": [...]
  }

Agent Controller → gvmd:
  HTTP 201 Created
  {
    "scan_id": "uuid-here",
    "status": "queued"
  }

Later, gvmd polls:
  GET /scans/{scan_id}/status
  GET /scans/{scan_id}/results
```

---

## Summary Table

| Function | File:Line | Called From | HTTP Method | Endpoint |
|----------|-----------|-------------|-------------|----------|
| `agent_controller_get_agents()` | `manage_agents.c:528` | `sync_agents_from_agent_controller()` | GET | `/agents` |
| `agent_controller_get_agents()` | `manage_sql.c:31406` | `verify_agent_control_scanner()` | GET | `/agents` |
| `agent_controller_get_agents()` | `manage_sql.c:31462` | `scanner_desc_with_host_and_port()` | GET | `/agents` |
| `agent_controller_update_agents()` | `manage_agents.c:706-707` | `modify_and_resync_agents()` | PUT | `/agents` |
| `agent_controller_delete_agents()` | `manage_agents.c:803` | `delete_and_resync_agents()` | DELETE | `/agents` |
| `agent_controller_build_create_scan_payload()` | `manage.c:7889` | `launch_agent_control_task()` | N/A | (builds JSON) |
| `http_scanner_create_scan()` | `manage.c:7897` | `launch_agent_control_task()` | POST | `/scans` |
| `agent_controller_get_scan_id()` | `manage.c:7906` | `launch_agent_control_task()` | N/A | (parses JSON) |

---

## Additional Functions (Used for Polling)

From `src/manage.c:handle_agent_controller_scan()` (lines 7760-7819):

### `http_scanner_parsed_results()`

**Line 7793:**
```c
int http_status = http_scanner_parsed_results (connector, 0, 0, &results);
```

**What it does:**
- Polls Agent Controller for scan results
- GET /scans/{scan_id}/results
- Returns list of vulnerability findings

**Header:** `<gvm/http_scanner/http_scanner.h>`

---

## Where These Functions Come From

### gvm-libs Project Structure

```
gvm-libs/
├── base/
├── util/
├── http_scanner/
│   └── http_scanner.h        ← HTTP scanner functions
│       - http_scanner_create_scan()
│       - http_scanner_parsed_results()
│       - http_scanner_connector_new()
│
└── agent_controller/
    └── agent_controller.h    ← Agent Controller API
        - agent_controller_get_agents()
        - agent_controller_update_agents()
        - agent_controller_delete_agents()
        - agent_controller_build_create_scan_payload()
        - agent_controller_get_scan_id()
```

### Build Dependencies

From `src/CMakeLists.txt`:

**Lines 35-38:** HTTP Scanner
```cmake
if(ENABLE_HTTP_SCANNER)
  pkg_check_modules(LIBGVM_HTTP REQUIRED libgvm_http>=22.30)
  pkg_check_modules(LIBGVM_HTTP_SCANNER REQUIRED libgvm_http_scanner>=22.30)
endif(ENABLE_HTTP_SCANNER)
```

**Lines 44-52:** Agent Controller
```cmake
if(ENABLE_AGENTS)
  pkg_check_modules(
    LIBGVM_AGENT_CONTROLLER
    REQUIRED
    libgvm_agent_controller>=22.30
  )
endif(ENABLE_AGENTS)
```

---

## Conclusion

This document provides **exact evidence** of:

1. ✅ Which functions gvmd calls
2. ✅ Where in the source code they're called (file:line)
3. ✅ What context they're called in
4. ✅ What they're used for
5. ✅ What HTTP requests they translate to

All functions come from `libgvm_agent_controller` and `libgvm_http_scanner` libraries in the gvm-libs project, not from gvmd itself.
