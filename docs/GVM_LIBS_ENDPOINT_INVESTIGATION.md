# Investigation Guide: Find Agent Controller API Endpoints in gvm-libs

## Context: What We Know So Far

From investigating the **gvmd codebase**, we discovered that gvmd is a **pure HTTP client** that calls wrapper functions from external libraries. The actual HTTP endpoints (like `/scans`, `/agents`, etc.) are **NOT defined in gvmd** - they're hard-coded in the **gvm-libs** project.

### Key Discovery from gvmd

**File:** `src/manage.c:7889-7906`

```c
// Step 1: Build JSON payload with list of agents to scan
payload = agent_controller_build_create_scan_payload (agent_control_list);

// Step 2: Send HTTP POST to Agent Controller
http_scanner_resp = http_scanner_create_scan (connection, payload);

// Step 3: Expects HTTP 201 Created response
if (!http_scanner_resp || http_scanner_resp->code != 201)
  {
    if (error) *error = g_strdup ("Scanner failed to create the scan");
    goto make_report;
  }

// Step 4: Parse scan_id from JSON response
gchar *scan_id = agent_controller_get_scan_id (http_scanner_resp->body);
```

**The functions we need to trace:**

1. `agent_controller_build_create_scan_payload()` - Builds JSON
2. `http_scanner_create_scan()` - Makes HTTP POST (endpoint unknown)
3. `agent_controller_get_scan_id()` - Parses response
4. `agent_controller_get_agents()` - GET request (endpoint unknown)
5. `agent_controller_update_agents()` - PUT request (endpoint unknown)
6. `agent_controller_delete_agents()` - DELETE request (endpoint unknown)

### Import Evidence

**File:** `src/manage_http_scanner.h:20`
```c
#include <gvm/http_scanner/http_scanner.h>
```

**File:** `src/manage_agents.h:24`
```c
#include <agent_controller/agent_controller.h>
```

**File:** `src/CMakeLists.txt:44-52` (Build dependency)
```cmake
if(ENABLE_AGENTS)
  pkg_check_modules(
    LIBGVM_AGENT_CONTROLLER
    REQUIRED
    libgvm_agent_controller>=22.30
  )
```

---

## Your Mission: Find the Endpoints

You need to clone the gvm-libs repository and find where these library functions make their HTTP requests. The endpoint paths will be string literals in the implementation files.

---

## Step 1: Clone gvm-libs Repository

```bash
# Clone the official Greenbone gvm-libs repository
git clone https://github.com/greenbone/gvm-libs.git
cd gvm-libs

# List the directory structure
ls -la

# Look for agent_controller and http_scanner directories
find . -type d -name "*agent*" -o -name "*http*" -o -name "*scanner*"
```

**Expected structure:**
```
gvm-libs/
├── base/
├── util/
├── http_scanner/         ← HTTP scanner implementation
│   ├── http_scanner.h    ← Function declarations
│   └── http_scanner.c    ← Implementation (endpoints here!)
├── agent_controller/     ← Agent Controller client implementation
│   ├── agent_controller.h
│   └── agent_controller.c
└── ...
```

---

## Step 2: Investigate http_scanner Directory

### Find the create_scan Implementation

```bash
cd http_scanner

# Search for the function definition
grep -n "http_scanner_create_scan" *.c *.h

# Look for HTTP method strings (POST, GET, PUT, DELETE)
grep -n "POST\|GET\|PUT\|DELETE" *.c

# Search for endpoint path patterns
grep -n '"/.*"' *.c | grep -E "scan|api|v1"

# Look for URL construction
grep -n "sprintf\|g_strdup_printf\|strcat" *.c | head -20
```

### What to Look For

**In `http_scanner.c`**, find the `http_scanner_create_scan()` function:

```c
// Example of what you might find:
http_scanner_resp_t
http_scanner_create_scan (http_scanner_connector_t connector, const char *payload)
{
  // Look for lines like:
  char *url = g_strdup_printf("%s://%s:%d/scans", ...);
  // or
  curl_easy_setopt(curl, CURLOPT_URL, "https://host/api/v1/scans");
  // or
  request_path = "/scans";
}
```

**Key things to extract:**
- ✅ Exact endpoint path (e.g., `/scans`, `/api/v1/scans`, etc.)
- ✅ HTTP method used (POST, GET, PUT, DELETE)
- ✅ How URL is constructed (base_url + path)
- ✅ Content-Type header (probably `application/json`)
- ✅ Expected response codes

---

## Step 3: Investigate agent_controller Directory

### Find Agent Management Endpoints

```bash
cd ../agent_controller

# Find function definitions
grep -n "agent_controller_get_agents\|agent_controller_update_agents\|agent_controller_delete_agents" *.c

# Look for HTTP methods
grep -n "GET\|PUT\|POST\|DELETE" *.c

# Search for /agents endpoint
grep -n '"/agents"' *.c

# Look for URL construction
grep -n "sprintf\|g_strdup_printf" *.c | grep -i agent
```

### Functions to Trace

Find the implementation for each of these:

#### 1. agent_controller_get_agents()
```c
// Expected: GET /agents or GET /api/v1/agents
// Returns: List of registered agents
```

#### 2. agent_controller_update_agents()
```c
// Expected: PUT /agents or PUT /agents/{id}
// Payload: Updated agent properties
```

#### 3. agent_controller_delete_agents()
```c
// Expected: DELETE /agents/{id}
// Returns: HTTP 204 No Content
```

#### 4. agent_controller_build_create_scan_payload()
```c
// This might just build JSON, not make HTTP request
// Look for JSON string construction
```

---

## Step 4: Document Your Findings

For each function, create a table like this:

### HTTP Scanner Functions

| Function | File:Line | HTTP Method | Endpoint Path | Expected Status | Notes |
|----------|-----------|-------------|---------------|-----------------|-------|
| `http_scanner_create_scan()` | http_scanner.c:XXX | POST | `/scans` | 201 Created | Creates new scan |
| `http_scanner_delete_scan()` | http_scanner.c:XXX | DELETE | `/scans/{id}` | 204 No Content | Deletes scan |
| `http_scanner_stop_scan()` | http_scanner.c:XXX | PUT/POST | `/scans/{id}/stop` | 204 No Content | Stops running scan |
| `http_scanner_parsed_scan_status()` | http_scanner.c:XXX | GET | `/scans/{id}/status` | 200 OK | Get scan status |
| `http_scanner_parsed_results()` | http_scanner.c:XXX | GET | `/scans/{id}/results` | 200 OK | Get scan results |

### Agent Controller Functions

| Function | File:Line | HTTP Method | Endpoint Path | Expected Status | Notes |
|----------|-----------|-------------|---------------|-----------------|-------|
| `agent_controller_get_agents()` | agent_controller.c:XXX | GET | `/agents` | 200 OK | List all agents |
| `agent_controller_update_agents()` | agent_controller.c:XXX | PUT | `/agents` | 200 OK | Update agents |
| `agent_controller_delete_agents()` | agent_controller.c:XXX | DELETE | `/agents` | 204 No Content | Delete agents |

---

## Step 5: Extract HTTP Request Examples

For each endpoint, document the actual HTTP request format:

### Example: Create Scan Endpoint

**Function:** `http_scanner_create_scan()`
**File:** `gvm-libs/http_scanner/http_scanner.c:XXX`

**HTTP Request:**
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
      "agent_id": "uuid-1",
      "hostname": "host1.example.com"
    },
    {
      "agent_id": "uuid-2",
      "hostname": "host2.example.com"
    }
  ]
}
```

**Expected Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

## Step 6: Look for API Versioning

Check if the API uses versioning:

```bash
# Search for /api/v1, /api/v2, etc.
grep -rn "/api/v" .

# Search for version in URL construction
grep -rn "version\|API_VERSION" *.c *.h

# Look for defines
grep -n "#define.*API\|VERSION" *.h
```

---

## Step 7: Check for Query Parameters

Some endpoints might use query parameters:

```bash
# Look for query string construction
grep -rn "?" *.c | grep -E "http|url|path"

# Common patterns:
# GET /scans/{id}/results?start=0&limit=100
# GET /agents?filter=authorized
```

---

## Alternative: Check CMakeLists or pkg-config

If the source is hard to read, check build files:

```bash
# Look at CMakeLists.txt
cat CMakeLists.txt | grep -i agent

# Check for installed headers (if gvm-libs is installed)
pkg-config --cflags libgvm_agent_controller
pkg-config --cflags libgvm_http_scanner

# Read installed headers
cat /usr/include/gvm/agent_controller/agent_controller.h
cat /usr/include/gvm/http_scanner/http_scanner.h
```

---

## What to Send Back

Please document:

### 1. **Scan Creation Endpoint**
- Full endpoint path
- HTTP method
- Request payload format
- Response format
- Expected status codes

### 2. **Agent Management Endpoints**
- GET /agents - List agents
- PUT /agents - Update agents
- DELETE /agents - Delete agents
- Full request/response examples

### 3. **Scan Status & Results Endpoints**
- GET /scans/{id}/status
- GET /scans/{id}/results
- Any pagination parameters

### 4. **API Base Path**
- Is it `/scans` or `/api/v1/scans`?
- Is there versioning?
- Is there a prefix?

### 5. **Code Evidence**
- File paths and line numbers
- Actual C code snippets showing URL construction
- Any #define constants for endpoints

---

## Quick Reference: Files to Check

**Priority 1 (Most Likely):**
```
gvm-libs/http_scanner/http_scanner.c       ← Scan endpoints
gvm-libs/agent_controller/agent_controller.c  ← Agent endpoints
```

**Priority 2 (Headers):**
```
gvm-libs/http_scanner/http_scanner.h
gvm-libs/agent_controller/agent_controller.h
```

**Priority 3 (Utilities):**
```
gvm-libs/util/http_client.c    ← Low-level HTTP client
gvm-libs/base/*                ← Base utilities
```

---

## Expected Outcome

You should find explicit endpoint paths like:

```c
// In http_scanner.c
#define SCAN_ENDPOINT "/scans"
#define API_VERSION "/api/v1"

http_scanner_resp_t
http_scanner_create_scan (http_scanner_connector_t connector, const char *payload)
{
  char *url = g_strdup_printf("%s://%s:%d%s%s",
    connector->protocol,
    connector->host,
    connector->port,
    API_VERSION,
    SCAN_ENDPOINT
  );
  // Makes: POST https://host:port/api/v1/scans
}
```

---

## Need Help?

If you can't find the endpoints, they might be:
1. In a different directory structure
2. Abstracted through another layer
3. Defined as macros or constants
4. In a newer/older version of gvm-libs

Try:
```bash
# Nuclear option: search everything
grep -r "/scans" gvm-libs/
grep -r "/agents" gvm-libs/
grep -r "POST\|GET\|PUT\|DELETE" gvm-libs/ | grep -i "scan\|agent"
```

Good luck! 🚀
