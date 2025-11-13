# Complete Agent Controller & HTTP Scanner API Specification

## Executive Summary

Based on investigation of **gvm-libs source code**, we now have definitive answers about how gvmd communicates with the Agent Controller service.

**Critical Discovery:** There are actually **TWO separate APIs**:

1. **HTTP Scanner API** - For scan operations (`/{prefix}/scans/*`)
2. **Agent Controller API** - For agent management (`/api/v1/admin/*`)

---

## Answer to Original Question

### "How does gvmd send a scan command to Agent Controller?"

**Answer:** When gvmd wants to scan agents 1, 2, and 3, it does this:

**Step 1: Build Agent List** (gvmd code)
```c
// src/manage.c:7867-7886
agent_uuids = agent_uuid_list_from_group(agent_group);
agent_control_list = agent_controller_agent_list_new(agent_uuids->count);
get_agent_controller_agents_from_uuids(scanner, agent_uuids, agent_control_list);
```

**Step 2: Build JSON Payload** (gvmd code)
```c
// src/manage.c:7889
payload = agent_controller_build_create_scan_payload(agent_control_list);
```

**Step 3: HTTP POST to Scanner API** (gvmd code → gvm-libs)
```c
// src/manage.c:7897
http_scanner_resp = http_scanner_create_scan(connection, payload);
```

**Step 4: What Actually Happens** (gvm-libs code)
```
Function: http_scanner_create_scan()
File: gvm-libs/http_scanner/http_scanner.c:505
HTTP Request:
  POST /{scan_prefix}/scans
  Content-Type: application/json

  {
    "agents": [
      {"agent_id": "uuid-1", "hostname": "host1"},
      {"agent_id": "uuid-2", "hostname": "host2"},
      {"agent_id": "uuid-3", "hostname": "host3"}
    ]
  }

Expected Response: HTTP 201 Created
  {
    "scan_id": "550e8400-e29b-41d4-a716-446655440000"
  }
```

**Default Endpoint:** `POST /scans`
**Configurable Endpoint:** `POST /api/v1/scans` (if scan_prefix="api/v1")

---

## Two APIs Explained

### API #1: HTTP Scanner API (Scan Operations)

**Purpose:** Create, manage, and monitor vulnerability scans
**Base Path:** `/{scan_prefix}/scans` (configurable, defaults to `/scans`)
**Used For:** Scan lifecycle management

| Operation | Method | Endpoint | Function | File:Line |
|-----------|--------|----------|----------|-----------|
| Create scan | POST | `/{prefix}/scans` | `http_scanner_create_scan()` | http_scanner.c:505 |
| Start scan | POST | `/{prefix}/scans/{id}` | `http_scanner_start_scan()` | http_scanner.c:576 |
| Stop scan | POST | `/{prefix}/scans/{id}` | `http_scanner_stop_scan()` | http_scanner.c:622 |
| Get status | GET | `/{prefix}/scans/{id}/status` | `http_scanner_get_scan_status()` | http_scanner.c:977 |
| Get results | GET | `/{prefix}/scans/{id}/results` | `http_scanner_get_scan_results()` | http_scanner.c:670 |
| Delete scan | DELETE | `/{prefix}/scans/{id}` | `http_scanner_delete_scan()` | http_scanner.c:1021 |
| Get preferences | GET | `/{prefix}/scans/preferences` | `http_scanner_get_scan_preferences()` | http_scanner.c:1358 |

**Health Checks:**
- `GET /health/alive` - http_scanner.c:1051
- `GET /health/ready` - http_scanner.c:1079
- `GET /health/started` - http_scanner.c:1107
- `HEAD /` - Version info (http_scanner.c:462)

### API #2: Agent Controller API (Agent Management)

**Purpose:** Manage agents, configurations, and updates
**Base Path:** `/api/v1/admin/` (always versioned, non-configurable)
**Authentication:** **Required** - API key passed with each request
**Used For:** Agent CRUD operations

| Operation | Method | Endpoint | Function | File:Line |
|-----------|--------|----------|----------|-----------|
| List agents | GET | `/api/v1/admin/agents` | `agent_controller_get_agents()` | agent_controller.c:807 |
| Update agents | **PATCH** | `/api/v1/admin/agents` | `agent_controller_update_agents()` | agent_controller.c:891 |
| Delete agents | **POST** | `/api/v1/admin/agents/delete` | `agent_controller_delete_agents()` | agent_controller.c:978 |
| Get scan config | GET | `/api/v1/admin/scan-agent-config` | `agent_controller_get_scan_agent_config()` | agent_controller.c:1123 |
| Update scan config | PUT | `/api/v1/admin/scan-agent-config` | `agent_controller_update_scan_agent_config()` | agent_controller.c:1183 |
| Get updates | GET | `/api/v1/admin/agents/updates` | `agent_controller_get_agent_updates()` | agent_controller.c:1241 |

---

## Key Architectural Insights

### 1. Two APIs, One Service

The "Agent Controller" service exposes **both APIs**:
- **Scanner API** at `/{prefix}/scans/*` - For scan operations
- **Admin API** at `/api/v1/admin/*` - For agent management

### 2. Non-Standard REST Design Choices

**Agent Controller API intentionally violates REST conventions:**

❌ **Update agents:** Uses `PATCH /api/v1/admin/agents` (not `PUT`)
- Reason: PATCH semantics for partial updates

❌ **Delete agents:** Uses `POST /api/v1/admin/agents/delete` (not `DELETE /agents/{id}`)
- Reason: Bulk delete operation with JSON payload

✅ **This is intentional** - Greenbone chose pragmatic API design over strict REST compliance

### 3. Configurable vs Fixed Paths

**HTTP Scanner API:** Configurable base path
```c
// gvm-libs/http_scanner/http_scanner.c:476-486
if (conn->scan_prefix != NULL)
  path = "/" + scan_prefix + "/scans";
else
  path = "/scans";
```

**Agent Controller API:** Fixed versioned path
```c
// Always: /api/v1/admin/*
```

### 4. Authentication Differences

| API | Authentication | Optional? |
|-----|----------------|-----------|
| HTTP Scanner | API key via connector | Yes (optional) |
| Agent Controller | API key in request | **No (required)** |

---

## Complete Scan Creation Flow

### gvmd Side (src/manage.c:7835-7945)

```c
// 1. Get task's scanner
scanner = task_scanner(task);

// 2. Connect to HTTP scanner
connection = http_scanner_connect(scanner, NULL);

// 3. Build agent UUID list from group
agent_uuids = agent_uuid_list_from_group(agent_group);

// 4. Map UUIDs to agent controller format
agent_control_list = agent_controller_agent_list_new(agent_uuids->count);
get_agent_controller_agents_from_uuids(scanner, agent_uuids, agent_control_list);

// 5. Build JSON payload
payload = agent_controller_build_create_scan_payload(agent_control_list);

// 6. Create scan (this is where HTTP POST happens)
http_scanner_resp = http_scanner_create_scan(connection, payload);

// 7. Expect HTTP 201 Created
if (http_scanner_resp->code != 201) {
  error = "Scanner failed to create the scan";
}

// 8. Extract scan_id from response
scan_id = agent_controller_get_scan_id(http_scanner_resp->body);
```

### gvm-libs Side (http_scanner/http_scanner.c:505)

```c
http_scanner_resp_t
http_scanner_create_scan(http_scanner_connector_t conn, const char *payload)
{
  // Build URL
  GString *path = build_path_prefix(conn);  // Returns "/{prefix}/scans"
  char *url = g_strdup_printf("%s://%s:%d%s",
    conn->protocol,   // "https"
    conn->host,       // "agent-controller.example.com"
    conn->port,       // 443
    path->str         // "/scans" or "/api/v1/scans"
  );

  // Make HTTP POST
  // POST https://agent-controller.example.com:443/scans
  // Content-Type: application/json
  // Body: {payload}

  return response;
}
```

---

## HTTP Request Examples

### 1. Create Scan

**Request:**
```http
POST /scans HTTP/1.1
Host: agent-controller.example.com:443
Content-Type: application/json
Content-Length: 256

{
  "scan_config": {
    "scan_type": "full_and_fast"
  },
  "agents": [
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440001",
      "hostname": "server1.example.com"
    },
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440002",
      "hostname": "server2.example.com"
    },
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440003",
      "hostname": "server3.example.com"
    }
  ]
}
```

**Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /scans/550e8400-e29b-41d4-a716-446655440000

{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### 2. Get Scan Status

**Request:**
```http
GET /scans/550e8400-e29b-41d4-a716-446655440000/status HTTP/1.1
Host: agent-controller.example.com:443
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 45,
  "agents_completed": 1,
  "agents_running": 2,
  "agents_total": 3,
  "start_time": 1705318200,
  "end_time": null
}
```

### 3. Get Scan Results (with pagination)

**Request:**
```http
GET /scans/550e8400-e29b-41d4-a716-446655440000/results?range=0-99 HTTP/1.1
Host: agent-controller.example.com:443
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "results": [
    {
      "result_id": "result-001",
      "agent_id": "550e8400-e29b-41d4-a716-446655440001",
      "hostname": "server1.example.com",
      "nvt": {
        "oid": "1.3.6.1.4.1.25623.1.0.12345",
        "name": "OpenSSH Obsolete Version Detection",
        "severity": 5.0,
        "cvss_base_vector": "AV:N/AC:L/Au:N/C:N/I:N/A:N"
      },
      "port": "22/tcp",
      "threat": "Medium",
      "description": "The remote SSH server is running an obsolete version."
    }
  ],
  "total_results": 245,
  "returned_results": 100
}
```

### 4. List Agents (Admin API)

**Request:**
```http
GET /api/v1/admin/agents HTTP/1.1
Host: agent-controller.example.com:443
X-API-Key: your-api-key-here
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "agents": [
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440001",
      "hostname": "server1.example.com",
      "authorized": true,
      "last_heartbeat": 1705318500,
      "status": "online",
      "version": "1.0.0"
    }
  ]
}
```

### 5. Update Agents (Admin API)

**Request:**
```http
PATCH /api/v1/admin/agents HTTP/1.1
Host: agent-controller.example.com:443
X-API-Key: your-api-key-here
Content-Type: application/json

{
  "agents": [
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440001",
      "authorized": true,
      "update_to_latest": true
    }
  ]
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "updated": 1,
  "failed": 0
}
```

### 6. Delete Agents (Admin API)

**Request:**
```http
POST /api/v1/admin/agents/delete HTTP/1.1
Host: agent-controller.example.com:443
X-API-Key: your-api-key-here
Content-Type: application/json

{
  "agent_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "deleted": 2,
  "failed": 0
}
```

---

## Configuration: scan_prefix

The HTTP Scanner API base path is configurable via the `scan_prefix` connector option.

### Default Configuration (No Prefix)
```c
// gvmd sets scan_prefix = NULL
connection = http_scanner_connector_new();
// Results in: POST /scans
```

### Versioned Configuration
```c
// gvmd sets scan_prefix = "api/v1"
http_scanner_connector_builder(conn, HTTP_SCANNER_SCAN_PREFIX, "api/v1");
// Results in: POST /api/v1/scans
```

### Path Construction Logic
```c
// gvm-libs/http_scanner/http_scanner.c:476-486
GString *path = g_string_new("");
if (conn->scan_prefix != NULL && conn->scan_prefix[0] != '\0') {
  g_string_append(path, "/");
  g_string_append(path, conn->scan_prefix);
}
g_string_append(path, "/scans");
// Returns: "/scans" or "/api/v1/scans"
```

---

## Summary: Complete API Specification

### HTTP Scanner API (Scan Operations)
**Base:** `/{prefix}/scans` (default: `/scans`)
**Auth:** Optional API key
**Format:** JSON

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/{prefix}/scans` | POST | Create scan |
| `/{prefix}/scans/{id}` | POST | Start/Stop scan |
| `/{prefix}/scans/{id}` | DELETE | Delete scan |
| `/{prefix}/scans/{id}/status` | GET | Get status |
| `/{prefix}/scans/{id}/results` | GET | Get results |
| `/{prefix}/scans/preferences` | GET | Get scan options |
| `/health/alive` | GET | Health check |
| `/health/ready` | GET | Health check |
| `/health/started` | GET | Health check |

### Agent Controller API (Agent Management)
**Base:** `/api/v1/admin/`
**Auth:** **Required** API key
**Format:** JSON

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/admin/agents` | GET | List agents |
| `/api/v1/admin/agents` | PATCH | Update agents |
| `/api/v1/admin/agents/delete` | POST | Delete agents |
| `/api/v1/admin/scan-agent-config` | GET | Get scan config |
| `/api/v1/admin/scan-agent-config` | PUT | Update scan config |
| `/api/v1/admin/agents/updates` | GET | Get available updates |

---

## Implementation Notes

### For Agent Controller Service Developers

When building an open-source Agent Controller service, you must implement:

1. **HTTP Scanner API** - For gvmd to create and manage scans
2. **Agent Controller API** - For gvmd to manage agents
3. **Agent-Facing API** - For agents to register, heartbeat, and pull jobs (not documented here - separate investigation needed)

### gvmd Communication Pattern

```
gvmd → HTTP Scanner API → Create Scan
  ↓
Agent Controller queues scan
  ↓
Agents poll Agent Controller for work (separate API)
  ↓
Agents execute scan locally
  ↓
Agents report results to Agent Controller
  ↓
gvmd → HTTP Scanner API → Poll for results
```

---

## Source Code References

### gvmd (Client Code)
- `src/manage.c:7835-7945` - Scan creation flow
- `src/manage_http_scanner.c:32-73` - HTTP scanner connection
- `src/manage_agents.c:522-705` - Agent synchronization

### gvm-libs (Server API Definitions)
- `http_scanner/http_scanner.c` - HTTP Scanner API implementation
- `agent_controller/agent_controller.c` - Agent Controller API implementation
- Both files in gvm-libs repository

---

## Credits

This specification was compiled through investigation of:
1. **gvmd source code** - Client-side behavior and expected responses
2. **gvm-libs source code** - Server-side endpoint definitions and HTTP methods

All endpoint paths, HTTP methods, and line numbers verified against actual source code.
