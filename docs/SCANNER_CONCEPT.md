# What is a "Scanner" in gvmd?

## Executive Summary

In the gvmd codebase, a **scanner** is a **registered external service** that performs vulnerability scans. It's essentially a **scan execution backend** that gvmd connects to via network protocols (HTTP, Unix sockets, etc.) to:

1. **Start** vulnerability scans
2. **Monitor** scan progress
3. **Retrieve** scan results
4. **Manage** scan lifecycle (stop, delete, resume)

Think of scanners as **"scan workers"** - gvmd orchestrates tasks, but scanners do the actual scanning work.

---

## Scanner Database Schema

**Location:** `src/manage_pg.c:2710-2724`

```sql
CREATE TABLE IF NOT EXISTS scanners (
  id SERIAL PRIMARY KEY,
  uuid text UNIQUE NOT NULL,
  owner integer REFERENCES users (id) ON DELETE RESTRICT,
  name text,
  comment text,
  host text,                    -- Scanner hostname/IP
  port integer,                 -- Scanner port
  type integer,                 -- Scanner type (see below)
  ca_pub text,                  -- CA certificate for TLS
  credential integer,           -- Authentication credential
  creation_time integer,
  modification_time integer,
  relay_host text,             -- Optional relay/proxy host
  relay_port integer           -- Optional relay/proxy port
);
```

---

## Scanner Types

**Location:** `src/manage.h:342-356`

```c
typedef enum scanner_type
{
  SCANNER_TYPE_NONE = 0,
  /* 1 was removed (SCANNER_TYPE_OSP) */
  SCANNER_TYPE_OPENVAS = 2,                      // Classic OpenVAS scanner
  SCANNER_TYPE_CVE = 3,                          // CVE data scanner
  /* 4 was removed (SCANNER_TYPE_GMP) */
  SCANNER_TYPE_OSP_SENSOR = 5,                   // OSP-based sensor
  SCANNER_TYPE_OPENVASD = 6,                     // OpenVAS daemon (new)
  SCANNER_TYPE_AGENT_CONTROLLER = 7,             // Agent Controller
  SCANNER_TYPE_OPENVASD_SENSOR = 8,              // OpenVAS daemon sensor
  SCANNER_TYPE_AGENT_CONTROLLER_SENSOR = 9,      // Agent Controller sensor
  SCANNER_TYPE_CONTAINER_IMAGE = 10,             // Container image scanner
  SCANNER_TYPE_MAX = 11,
} scanner_type_t;
```

### Scanner Type Categories

| Type | Purpose | Protocol | Notes |
|------|---------|----------|-------|
| **OPENVAS (2)** | Traditional vulnerability scanner | Unix socket/OSP | Most common, scans networks |
| **CVE (3)** | CVE database scanner | N/A | Data-only, no active scanning |
| **OSP_SENSOR (5)** | Remote OSP sensor | OSP over network | Distributed scanning |
| **OPENVASD (6)** | New OpenVAS daemon | HTTP/HTTPS | Next-gen OpenVAS |
| **AGENT_CONTROLLER (7)** | Agent management service | HTTP/HTTPS | Manages deployed agents |
| **OPENVASD_SENSOR (8)** | Remote OpenVAS daemon | HTTP/HTTPS | Distributed next-gen |
| **AGENT_CONTROLLER_SENSOR (9)** | Remote agent controller | HTTP/HTTPS | Distributed agent mgmt |
| **CONTAINER_IMAGE (10)** | Container/OCI scanner | HTTP/HTTPS | Container vulnerability scanning |

---

## Scanner Properties

### Core Properties (from database schema)

```c
// Connection details
char *host;           // "localhost", "192.168.1.100", "scanner.example.com"
int port;             // 22, 80, 443, 9390, etc.
int type;             // SCANNER_TYPE_* enum value

// Security (TLS/Authentication)
char *ca_pub;         // CA certificate for HTTPS
char *key_pub;        // Client certificate (public key)
char *key_priv;       // Client certificate (private key)
int credential;       // Reference to credentials table

// Optional relay/proxy
char *relay_host;     // Proxy hostname
int relay_port;       // Proxy port

// Metadata
char *uuid;           // Unique identifier
char *name;           // Human-readable name
char *comment;        // Description
int owner;            // User who owns this scanner
```

### Scanner Functions (from `manage.h`)

```c
// Accessors
char *scanner_host(scanner_t, gboolean use_relay);
int scanner_port(scanner_t, gboolean use_relay);
int scanner_type(scanner_t);
char *scanner_ca_pub(scanner_t);
char *scanner_key_pub(scanner_t);
char *scanner_key_priv(scanner_t);

// Capabilities
gboolean scanner_has_relay(scanner_t);
int scanner_type_supports_unix_sockets(scanner_type_t);
int scanner_type_valid(scanner_type_t);
```

---

## HTTP Scanner Implementation

### Connection Process

**Location:** `src/manage_http_scanner.c:32-73`

The `http_scanner_connect()` function shows how gvmd connects to HTTP-based scanners:

```c
http_scanner_connector_t http_scanner_connect(scanner_t scanner,
                                               const char *scan_id)
{
  // 1. Get scanner properties from database
  host = scanner_host(scanner, has_relay);
  port = scanner_port(scanner, has_relay);
  ca_pub = scanner_ca_pub(scanner);
  key_pub = scanner_key_pub(scanner);
  key_priv = scanner_key_priv(scanner);

  // 2. Determine protocol
  if (ca_pub && key_pub && key_priv)
    protocol = "https";  // TLS with mutual auth
  else
    protocol = "http";   // Plain HTTP

  // 3. Build connector
  connection = http_scanner_connector_new();
  http_scanner_connector_builder(connection, HTTP_SCANNER_HOST, host);
  http_scanner_connector_builder(connection, HTTP_SCANNER_PORT, &port);
  http_scanner_connector_builder(connection, HTTP_SCANNER_PROTOCOL, protocol);
  http_scanner_connector_builder(connection, HTTP_SCANNER_CA_CERT, ca_pub);
  http_scanner_connector_builder(connection, HTTP_SCANNER_CERT, key_pub);
  http_scanner_connector_builder(connection, HTTP_SCANNER_KEY, key_priv);

  if (scan_id)
    http_scanner_connector_builder(connection, HTTP_SCANNER_SCAN_ID, scan_id);

  return connection;
}
```

### Scanner API Operations

HTTP-based scanners expose a REST-like API:

| Operation | Purpose | Implementation |
|-----------|---------|----------------|
| **Get scan status** | Check if scan exists, get progress | `http_scanner_parsed_scan_status()` |
| **Get scan progress** | Poll scan completion % | `http_scanner_get_scan_progress()` |
| **Get scan results** | Retrieve vulnerability findings | `http_scanner_parsed_results()` |
| **Stop scan** | Interrupt running scan | `http_scanner_stop_scan()` |
| **Delete scan** | Remove scan data | `http_scanner_delete_scan()` |

### Scan Status States

**Location:** `src/manage_http_scanner.c:100-176`

```c
typedef enum {
  HTTP_SCANNER_SCAN_STATUS_REQUESTED,   // Scan created, not started
  HTTP_SCANNER_SCAN_STATUS_STORED,      // Scan queued
  HTTP_SCANNER_SCAN_STATUS_RUNNING,     // Scan in progress
  HTTP_SCANNER_SCAN_STATUS_SUCCEEDED,   // Scan completed successfully
  HTTP_SCANNER_SCAN_STATUS_STOPPED,     // Scan manually stopped
  HTTP_SCANNER_SCAN_STATUS_FAILED,      // Scan failed with error
  HTTP_SCANNER_SCAN_STATUS_ERROR        // Scanner error
} http_scanner_scan_status_t;
```

### Scan Lifecycle Handling

**Location:** `src/manage_http_scanner.c:196-388`

The `handle_http_scanner_scan()` function shows the complete scan lifecycle:

```
1. Connect to scanner
   ↓
2. Poll scan status every 5 seconds
   ↓
3. Update task status in gvmd:
   - STORED → QUEUED
   - RUNNING → RUNNING
   ↓
4. Stream results back to gvmd
   - Parse vulnerability data
   - Insert into reports table
   ↓
5. Handle completion:
   - SUCCEEDED (100%) → Delete scan, return success
   - STOPPED → Delete scan, return error
   - FAILED → Delete scan, return error
   ↓
6. Cleanup connection
```

**Key Features:**
- **Retry logic**: Connection retry on failure (configurable)
- **Progress tracking**: Updates gvmd task progress (0-100%)
- **Incremental results**: Streams results as scan progresses
- **Error handling**: Graceful handling of scanner failures

---

## Scanner Use Cases by Type

### 1. SCANNER_TYPE_OPENVAS (Traditional)

**Use Case:** Network vulnerability scanning via OpenVAS scanner

**Connection:**
- Unix socket: `/run/ospd/ospd-openvas.sock`
- Protocol: OSP (OpenVAS Scanning Protocol)

**Characteristics:**
- Local scanner process
- Runs on same host as gvmd (typically)
- Direct socket communication
- Most mature/stable scanner type

---

### 2. SCANNER_TYPE_AGENT_CONTROLLER

**Use Case:** Manage deployed agents for remote scanning

**Connection:**
- Network: `http://agent-controller:8080` or `https://...`
- Protocol: HTTP REST API

**Characteristics:**
- Centralized agent management
- Agents deployed on target systems
- Pull-based scanning (agents phone home)
- Requires Agent Controller service

**Related Components:**
- Agent table (stores agent metadata)
- Agent groups (organize agents)
- Agent installers (deploy agents to systems)

---

### 3. SCANNER_TYPE_CONTAINER_IMAGE

**Use Case:** Scan container images for vulnerabilities

**Connection:**
- Network: `http://container-scanner:8080`
- Protocol: HTTP REST API

**Characteristics:**
- Specialized for Docker/OCI images
- Scans image layers
- CVE detection in packages
- No network scanning

---

### 4. SCANNER_TYPE_OPENVASD (Next-Gen)

**Use Case:** Modern HTTP-based OpenVAS scanner

**Connection:**
- Network: `http://openvasd:3000` or `https://...`
- Protocol: HTTP REST API

**Characteristics:**
- HTTP instead of Unix sockets
- More scalable/distributed
- Similar functionality to classic OpenVAS
- Cleaner API design

---

## Scanner vs. Task vs. Target Relationship

```
┌──────────┐
│  TASK    │ ← What to scan (orchestration)
└────┬─────┘
     │
     ├─→ ┌──────────┐
     │   │  TARGET  │ ← Where to scan (hosts/IPs)
     │   └──────────┘
     │
     ├─→ ┌──────────┐
     │   │  CONFIG  │ ← How to scan (NVT selection)
     │   └──────────┘
     │
     └─→ ┌──────────┐
         │ SCANNER  │ ← Who scans (scan engine)
         └──────────┘
              ↓
         ┌──────────┐
         │  REPORT  │ ← Scan results
         └──────────┘
```

**Flow:**
1. User creates **task** combining target + config + scanner
2. gvmd sends scan request to **scanner**
3. Scanner performs scan on **target** using **config**
4. Scanner returns results to gvmd
5. gvmd stores results in **report**

---

## Key Takeaways

### What a Scanner IS:
✅ An **external service** that executes scans
✅ A **registered resource** in gvmd's database
✅ A **network endpoint** (host:port) with credentials
✅ A **scan execution backend** with a defined API
✅ A **worker** that gvmd delegates scanning to

### What a Scanner is NOT:
❌ Built into gvmd (it's external)
❌ A static configuration (it's a runtime service)
❌ Part of the frontend (it's backend infrastructure)
❌ A scanner instance (one scanner can handle multiple scans)

---

## Practical Examples

### Example 1: Classic OpenVAS Scanner

```sql
INSERT INTO scanners (uuid, name, host, port, type) VALUES (
  '08b69003-5fc2-4037-a479-93b440211c73',
  'OpenVAS Default',
  '/run/ospd/ospd-openvas.sock',  -- Unix socket
  0,                               -- No port (socket)
  2                                -- SCANNER_TYPE_OPENVAS
);
```

### Example 2: Agent Controller (HTTP)

```sql
INSERT INTO scanners (uuid, name, host, port, type, ca_pub) VALUES (
  'b993b6f5-f9fb-4e6e-9c94-dd46c00e058d',
  'Agent Controller',
  'agent-controller.example.com',
  443,                             -- HTTPS
  7,                               -- SCANNER_TYPE_AGENT_CONTROLLER
  '-----BEGIN CERTIFICATE-----...' -- TLS CA cert
);
```

### Example 3: OpenVASD Scanner (HTTP)

```sql
INSERT INTO scanners (uuid, name, host, port, type) VALUES (
  'c1234567-89ab-cdef-0123-456789abcdef',
  'OpenVASD Scanner',
  'openvasd.local',
  3000,                            -- HTTP port
  6                                -- SCANNER_TYPE_OPENVASD
);
```

---

## Summary for Agent Controller Context

When you build an **Agent Controller service** (per the feasibility docs), you're building:

1. **A scanner** (type 7: SCANNER_TYPE_AGENT_CONTROLLER)
2. That runs as **an HTTP service** (like the HTTP scanner implementation)
3. That gvmd **connects to** (registers in scanners table)
4. To **manage agents** and **execute scans** on remote systems
5. Using the **same patterns** as other HTTP-based scanners

The HTTP scanner files show you exactly how gvmd:
- Connects to HTTP-based scanners
- Polls for scan progress
- Retrieves results
- Handles errors and retries

This is the **interface contract** your Agent Controller must implement!
