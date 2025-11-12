# What Agent Binaries Need to Execute Scans

## TL;DR Answer to "Do agents just download instructions?"

**NO.** Agents need BOTH:

1. ✅ **Scanning Engine** (NASL interpreter built into agent binary)
2. ✅ **NVT Feed** (vulnerability test scripts synced locally to agent)
3. ✅ **Scan Instructions** (downloaded dynamically from Agent Controller)

The agent is **NOT** a simple "runner" that downloads executable code. It's a **full vulnerability scanner** that receives instructions on **WHICH** pre-existing tests to run and **HOW** to run them.

---

## Architecture: Agent = OpenVAS Scanner + Polling Logic

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Binary                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Polling Loop (heartbeat, job fetching)              │
│  2. NASL Interpreter (executes vulnerability tests)     │
│  3. NVT Feed Manager (syncs test scripts)               │
│  4. Result Collector (formats and submits findings)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │
         │ Needs local access to:
         ├─ NVT Feed (vulnerability test scripts)
         ├─ Config database (preferences)
         └─ System resources (scan localhost)
```

**Think of it like:**
- **Agent = Firefox browser** (has rendering engine built-in)
- **NVT Feed = Webpage HTML** (content to process)
- **Scan Job = URL** (tells which page to render)

The agent doesn't download the rendering engine every time - it already has it. It just downloads instructions on which content to process.

---

## Evidence: What gvmd Sends in POST /scans

### Source Code: src/manage.c:7358-7499

Let me break down exactly what gvmd sends to the scanner (Agent Controller):

### 1. List of VT OIDs (Vulnerability Test Identifiers)

**Code:** src/manage.c:7366-7390

```c
// Initialize VTs list
vts = NULL;
vts_hash_table = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);

// Iterate through vulnerability test families
init_family_iterator(&families, 0, NULL, 1);
while (next(&families))
{
  const char *family = family_iterator_name(&families);
  if (family)
    {
      iterator_t nvts;
      // Get NVTs from the config for this family
      init_nvt_iterator(&nvts, 0, config, family, NULL, 1, NULL);
      while (next(&nvts))
        {
          const char *oid;  // <- OID: "1.3.6.1.4.1.25623.1.0.12345"
          openvasd_vt_single_t *new_vt;

          oid = nvt_iterator_oid(&nvts);
          new_vt = openvasd_vt_single_new(oid);  // Just the OID reference!

          vts = g_slist_prepend(vts, new_vt);
          g_hash_table_replace(vts_hash_table, g_strdup(oid), new_vt);
        }
      cleanup_iterator(&nvts);
    }
}
cleanup_iterator(&families);
```

**What this means:**
- gvmd reads the **scan config** (e.g., "Full and Fast")
- The config references NVTs by their **OID** (Object Identifier)
- gvmd builds a list of OIDs: `["1.3.6.1.4.1.25623.1.0.10662", "1.3.6.1.4.1.25623.1.0.10663", ...]`
- **gvmd does NOT send the actual NVT scripts** - only their identifiers!

**Example OIDs:**
```
1.3.6.1.4.1.25623.1.0.10662  <- "SSH Server Detection"
1.3.6.1.4.1.25623.1.0.10881  <- "OpenSSH Detection"
1.3.6.1.4.1.25623.1.0.12345  <- "Apache Version Detection"
```

### 2. Scanner Preferences (Global Settings)

**Code:** src/manage.c:7402-7443

```c
// Setup general scanner preferences
scanner_options = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, g_free);
init_preference_iterator(&scanner_prefs_iter, config, "SERVER_PREFS");
while (next(&scanner_prefs_iter))
{
  const char *name, *value;
  name = preference_iterator_name(&scanner_prefs_iter);
  value = preference_iterator_value(&scanner_prefs_iter);

  // Convert boolean preferences
  if (strcmp(value, "no") == 0)
    openvasd_value = "0";
  else if (strcmp(value, "yes") == 0)
    openvasd_value = "1";

  g_hash_table_replace(scanner_options, g_strdup(name), g_strdup(openvasd_value));
}

// Add task-specific preferences
max_checks = task_preference_value(task, "max_checks");
g_hash_table_insert(scanner_options, g_strdup("max_checks"),
                    max_checks ? max_checks : g_strdup(MAX_CHECKS_DEFAULT));

max_hosts = task_preference_value(task, "max_hosts");
g_hash_table_insert(scanner_options, g_strdup("max_hosts"),
                    max_hosts ? max_hosts : g_strdup(MAX_HOSTS_DEFAULT));
```

**Example Preferences:**
```json
{
  "max_checks": "4",
  "max_hosts": "20",
  "optimize_test": "1",
  "port_range": "1-65535",
  "safe_checks": "1",
  "unscanned_closed": "1",
  "unscanned_closed_udp": "0"
}
```

### 3. VT-Specific Preferences (Per-Test Settings)

**Code:** src/manage.c:7459-7499

```c
// Setup VT preferences (per-test configuration)
init_preference_iterator(&prefs, config, "PLUGINS_PREFS");
while (next(&prefs))
{
  const char *full_name, *value;
  openvasd_vt_single_t *openvasd_vt;
  gchar **split_name;

  full_name = preference_iterator_name(&prefs);  // "OID:pref_id:type:name"
  value = preference_iterator_value(&prefs);
  split_name = g_strsplit(full_name, ":", 4);

  if (split_name && split_name[0] && split_name[1] && split_name[2])
    {
      const char *oid = split_name[0];         // "1.3.6.1.4.1.25623.1.0.12345"
      const char *pref_id = split_name[1];     // "1"
      const char *type = split_name[2];        // "checkbox" | "radio" | "file" | ...

      // Handle different preference types
      if (strcmp(type, "checkbox") == 0)
        {
          if (strcmp(value, "yes") == 0)
            openvasd_value = g_strdup("1");
          else
            openvasd_value = g_strdup("0");
        }
      else if (strcmp(type, "file") == 0)
        openvasd_value = g_base64_encode((guchar*)value, strlen(value));

      openvasd_vt = g_hash_table_lookup(vts_hash_table, oid);
      if (openvasd_vt)
        openvasd_vt_single_add_value(openvasd_vt, pref_id,
                                     openvasd_value ? openvasd_value : value);
    }
}
```

**What this does:**
- Each VT (vulnerability test) can have its own preferences
- Format: `"<OID>:<pref_id>:<type>:<name>"`
- Example: `"1.3.6.1.4.1.25623.1.0.12345:1:checkbox:Enable HTTPS scanning"`

**Example VT Preferences:**
```json
{
  "vt_oid": "1.3.6.1.4.1.25623.1.0.12345",
  "preferences": {
    "1": "1",                    // Enable HTTPS
    "2": "443",                  // HTTPS port
    "3": "medium"                // Aggressiveness level
  }
}
```

### 4. Target Information

**Code:** src/manage.c:7281-7357

```c
// Set up target(s)
hosts_str = target_hosts(target);              // "192.168.1.0/24"
ports_str = target_port_range(target);         // "1-65535"
exclude_hosts_str = target_exclude_hosts(target);

// Alive tests (host discovery)
if (target_alive_tests(target) > 0)
  alive_test = target_alive_tests(target);

// Credentials for authenticated scanning
ssh_credential = (openvasd_credential_t *)target_osp_ssh_credential(target);
if (ssh_credential)
  openvasd_target_add_credential(openvasd_target, ssh_credential);

smb_credential = (openvasd_credential_t *)target_osp_smb_credential(target);
if (smb_credential)
  openvasd_target_add_credential(openvasd_target, smb_credential);
```

**Example Target Config:**
```json
{
  "hosts": "192.168.1.100",      // For agent-based scanning: likely "localhost"
  "ports": "1-65535",
  "exclude_hosts": "",
  "alive_test_methods": {
    "icmp": true,
    "tcp_syn": true,
    "tcp_ack": false,
    "arp": false,
    "consider_alive": false
  },
  "credentials": {
    "ssh": {
      "username": "admin",
      "password": "encrypted_password",
      "port": 22
    },
    "smb": {
      "username": "Administrator",
      "password": "encrypted_password"
    }
  }
}
```

---

## Complete JSON Payload Sent to Agent Controller

Based on the code above, the `POST /scans` request looks like:

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "targets": [
    {
      "hosts": "localhost",
      "ports": "1-65535",
      "exclude_hosts": "",
      "alive_test_methods": {
        "icmp": true,
        "tcp_syn": true
      },
      "credentials": {
        "ssh": {
          "username": "root",
          "password": "encrypted",
          "port": 22
        }
      }
    }
  ],
  "scanner_preferences": {
    "max_checks": "4",
    "max_hosts": "20",
    "optimize_test": "1",
    "safe_checks": "1"
  },
  "vts": [
    {
      "vt_id": "1.3.6.1.4.1.25623.1.0.10662",
      "preferences": {
        "1": "443",
        "2": "1"
      }
    },
    {
      "vt_id": "1.3.6.1.4.1.25623.1.0.10881",
      "preferences": {}
    },
    {
      "vt_id": "1.3.6.1.4.1.25623.1.0.12345",
      "preferences": {
        "1": "1",
        "2": "medium"
      }
    }
  ],
  "agents": [
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440001",
      "hostname": "server1.example.com"
    },
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440002",
      "hostname": "server2.example.com"
    }
  ]
}
```

**Notice:**
- ✅ VTs referenced by **OID only** (not full script code)
- ✅ Preferences for each VT
- ✅ Target configuration
- ✅ Scanner settings
- ❌ **NO actual VT script code sent!**

---

## What the Agent MUST Have Locally

### 1. NASL Interpreter (Scanning Engine)

**Required:** Built into agent binary

The agent must be able to execute NASL (Nessus Attack Scripting Language) scripts. This is the core scanning engine.

**Components:**
- NASL parser and interpreter
- Network stack (TCP/UDP socket management)
- Protocol implementations (HTTP, HTTPS, SSH, SMB, SNMP, etc.)
- Cryptography libraries (TLS, SSH keys, etc.)
- Result formatter

**Similar to:**
- OpenVAS Scanner (`openvassd`)
- Nessus Scanner
- QualysGuard Agent

### 2. NVT Feed (Vulnerability Test Scripts)

**Required:** Synced locally to agent filesystem

The NVT feed is a collection of `.nasl` files (vulnerability test scripts) organized by OID.

**Example Directory Structure:**
```
/var/lib/agent/plugins/
├── 2024/
│   ├── gb_ssh_detect.nasl                    # OID: 1.3.6.1.4.1.25623.1.0.10662
│   ├── gb_openssh_detect.nasl                # OID: 1.3.6.1.4.1.25623.1.0.10881
│   └── gb_apache_http_server_detect.nasl     # OID: 1.3.6.1.4.1.25623.1.0.12345
├── 2023/
│   └── ...
└── plugin_feed_info.inc
```

**How agents get the feed:**
1. Download from Greenbone Security Feed (requires subscription)
2. Sync from rsync server: `rsync://feed.community.greenbone.net/nvt-feed`
3. Sync from Agent Controller (if it caches the feed)

**Feed Update Mechanism:**
```bash
# Agent startup
agent --update-feed

# Periodic sync (e.g., daily via cron from agent config)
# scheduler_cron_time: ["0 2 * * *"]  <- 2 AM daily
agent --sync-feed
```

### 3. OID → NASL File Mapping

When the agent receives OID `1.3.6.1.4.1.25623.1.0.10662`, it must:

1. Look up the OID in the local NVT database
2. Find the corresponding `.nasl` file
3. Load the script into the NASL interpreter
4. Execute the script against the target
5. Collect results

**Mapping Database Example:**
```sql
-- NVT cache database (SQLite or similar)
CREATE TABLE nvts (
  oid TEXT PRIMARY KEY,
  name TEXT,
  family TEXT,
  filename TEXT,
  version TEXT,
  last_modification INTEGER
);

INSERT INTO nvts VALUES (
  '1.3.6.1.4.1.25623.1.0.10662',
  'SSH Server Detection',
  'Service detection',
  '/var/lib/agent/plugins/2024/gb_ssh_detect.nasl',
  '2024-01-15',
  1705318800
);
```

---

## Agent Execution Flow

### When Agent Receives Scan Job

```
Agent polls:
  GET /api/v1/agents/jobs

Agent Controller responds:
  {
    "jobs": [{
      "job_id": "job-12345",
      "scan_id": "550e8400-...",
      "config": {
        "vts": [
          {"vt_id": "1.3.6.1.4.1.25623.1.0.10662", "preferences": {...}},
          {"vt_id": "1.3.6.1.4.1.25623.1.0.10881", "preferences": {...}}
        ],
        "targets": [{...}],
        "scanner_preferences": {...}
      }
    }]
  }

Agent execution:
  1. Check if NVT feed is up-to-date
     └─ If stale: sync feed first

  2. FOR EACH vt_id in job config:
     a. Lookup OID in local NVT database
        SELECT filename FROM nvts WHERE oid = '1.3.6.1.4.1.25623.1.0.10662';
        → '/var/lib/agent/plugins/2024/gb_ssh_detect.nasl'

     b. Load NASL script from filesystem
        script_content = read_file('/var/lib/agent/plugins/2024/gb_ssh_detect.nasl');

     c. Set VT preferences
        set_kb_item("1.3.6.1.4.1.25623.1.0.10662/1", "443");

     d. Execute NASL script against target (localhost)
        result = nasl_interpreter.execute(script_content, target="localhost");

     e. Collect results
        if (result.vulnerable):
          results.append({
            "nvt_oid": "1.3.6.1.4.1.25623.1.0.10662",
            "host": "localhost",
            "port": "22/tcp",
            "severity": result.severity,
            "description": result.description
          });

  3. Submit results to Agent Controller
     POST /api/v1/agents/jobs/job-12345/results
     {
       "results": [...]
     }
```

---

## Why Can't Agents Just "Download Instructions"?

### Security Concerns

If agents downloaded executable code dynamically:
- ❌ **Code injection risk** - Malicious actor compromises Agent Controller, pushes malicious code
- ❌ **Integrity verification** - Hard to verify code hasn't been tampered with
- ❌ **Supply chain attack** - Man-in-the-middle could inject malicious tests

### Performance Concerns

If agents downloaded NVT scripts on-demand:
- ❌ **Bandwidth waste** - Each agent downloads ~100MB+ of scripts per scan
- ❌ **Latency** - Scan start delayed by download time
- ❌ **Network dependency** - Agents couldn't scan if disconnected from controller

### OpenVAS Architecture Inheritance

This design comes from OpenVAS, which has always worked this way:
- ✅ **NVT feed is signed** - GPG signatures verify integrity
- ✅ **Feed is cached locally** - Fast scan startup
- ✅ **Feed updated independently** - Can update without restarting scanner
- ✅ **Offline scanning possible** - Agents can scan even if controller is down

---

## What Agents Need to Be Built

### Minimum Viable Agent

```
1. Core Components:
   ✅ NASL interpreter (fork of OpenVAS scanner engine)
   ✅ NVT feed sync mechanism (rsync or HTTP)
   ✅ OID → NASL file database (SQLite)
   ✅ Network scanning capabilities
   ✅ Result formatter (JSON output)

2. Polling Logic:
   ✅ Heartbeat sender (POST /api/v1/agents/heartbeat)
   ✅ Job fetcher (GET /api/v1/agents/jobs)
   ✅ Result submitter (POST /api/v1/agents/jobs/{id}/results)
   ✅ Config retriever (GET /api/v1/agents/config)

3. System Integration:
   ✅ Local credentials (SSH keys, passwords)
   ✅ Filesystem access (read local files for auditing)
   ✅ Process execution (run system commands)
   ✅ Network access (scan localhost ports)

4. Configuration:
   ✅ Agent ID (UUID)
   ✅ Controller URL
   ✅ Authentication token/certificate
   ✅ NVT feed source
   ✅ Scan throttling settings
```

### Agent Binary Size

**Estimated:**
- Agent binary: ~10-20 MB (includes NASL interpreter)
- NVT feed: ~100-200 MB (thousands of `.nasl` files)
- Total disk usage: ~150-250 MB

---

## Comparison: gvmd Architecture vs Agent Architecture

### Traditional OpenVAS (gvmd → openvassd)

```
gvmd (manager)
  │
  ↓ OSP protocol (sends VT list + preferences)
  │
openvassd (scanner)
  ├─ Has NASL interpreter
  ├─ Has NVT feed (/var/lib/openvas/plugins/)
  └─ Scans remote targets
```

### Agent-Based Architecture (gvmd → Agent Controller → Agents)

```
gvmd (manager)
  │
  ↓ HTTP Scanner API (POST /scans with VT list + preferences)
  │
Agent Controller (service)
  │
  ↓ Agent-Facing API (job queue)
  │
Agents (host-based scanners)
  ├─ Has NASL interpreter
  ├─ Has NVT feed (/opt/agent/plugins/)
  └─ Scans localhost (endpoint scanning)
```

**Key Difference:**
- Traditional: Scanner scans **remote** targets (network scanning)
- Agent-based: Agent scans **localhost** (endpoint scanning with privileged access)

---

## Example: What an Agent Needs to Scan for OpenSSH Vulnerability

### 1. NVT Script (Must Be Local)

**File:** `/var/lib/agent/plugins/2024/gb_openssh_detect.nasl`

```nasl
# OpenSSH Detection
# OID: 1.3.6.1.4.1.25623.1.0.10881

if(description)
{
  script_oid("1.3.6.1.4.1.25623.1.0.10881");
  script_version("2024-01-15");
  script_name("OpenSSH Detection");
  script_category(ACT_GATHER_INFO);
  script_family("Service detection");
  script_dependencies("ssh_detect.nasl");
  script_require_ports("Services/ssh", 22);

  exit(0);
}

include("ssh_func.inc");
include("host_details.inc");

port = get_service(default:22, ipproto:"tcp");
banner = get_ssh_server_banner(port:port);

if(banner && "OpenSSH" >< banner)
{
  version = eregmatch(pattern:"OpenSSH_([0-9.]+[p0-9]*)", string:banner);
  if(version[1])
  {
    set_kb_item(name:"OpenSSH/version", value:version[1]);
    register_product(cpe:"cpe:/a:openbsd:openssh", location:"/", port:port);

    log_message(
      port: port,
      data: "OpenSSH version " + version[1] + " detected on port " + port
    );
  }
}
```

### 2. Scan Job (Downloaded from Agent Controller)

```json
{
  "job_id": "job-12345",
  "vts": [
    {
      "vt_id": "1.3.6.1.4.1.25623.1.0.10881",
      "preferences": {}
    }
  ],
  "targets": [
    {
      "hosts": "localhost",
      "ports": "22"
    }
  ],
  "scanner_preferences": {
    "safe_checks": "1"
  }
}
```

### 3. Agent Execution

```python
# Pseudocode for agent execution

def execute_scan(job):
    # Lookup NVT script
    nvt = database.get_nvt_by_oid("1.3.6.1.4.1.25623.1.0.10881")
    script_path = nvt.filename  # "/var/lib/agent/plugins/2024/gb_openssh_detect.nasl"

    # Load script
    script_content = read_file(script_path)

    # Execute NASL script
    result = nasl_interpreter.execute(
        script=script_content,
        target="localhost",
        port=22,
        preferences={}
    )

    # Collect result
    if result.messages:
        return {
            "nvt_oid": "1.3.6.1.4.1.25623.1.0.10881",
            "host": "localhost",
            "port": "22/tcp",
            "message": "OpenSSH version 8.2p1 detected on port 22",
            "severity": 0.0,  # Info only
            "qod": 80
        }
```

---

## Summary: Three-Layer Architecture

### Layer 1: gvmd (Manager)
**Responsibilities:**
- User interface (GMP API)
- Task scheduling
- Report management
- Scan configuration (which VTs, which targets)

**Does NOT have:**
- NVT feed
- NASL interpreter
- Scanning capabilities

### Layer 2: Agent Controller (Coordinator)
**Responsibilities:**
- Receive scan requests from gvmd
- Queue jobs for agents
- Track agent status
- Aggregate results from multiple agents
- Serve results to gvmd

**Does NOT have:**
- NASL interpreter
- Scanning capabilities
- **MAY** cache NVT feed (optional, for agent sync)

### Layer 3: Agents (Scanners)
**Responsibilities:**
- Poll for scan jobs
- Execute VTs locally (with NASL interpreter)
- Scan localhost with full system access
- Submit results to Agent Controller

**MUST have:**
- ✅ NASL interpreter (built into binary)
- ✅ NVT feed (synced locally)
- ✅ Full scanner engine
- ✅ System access (privileged)

---

## Final Answer

**Q: Would it not be enough to just build an agent binary?**

**A:** No. You need:
1. Agent binary (with NASL interpreter)
2. NVT feed sync mechanism
3. Full scanning engine

**Q: Would there need to be some scanner engine?**

**A:** Yes! The agent IS the scanner engine. It's essentially a copy of OpenVAS scanner that runs locally.

**Q: Would that exe be able to pull down "instructions" on how to complete the scan?**

**A:** Partially. The agent pulls down:
- ✅ **Which VTs to run** (OID list)
- ✅ **How to run them** (preferences)
- ✅ **What to scan** (targets, ports)
- ❌ **NOT the actual vulnerability test code** (that's local)

**Q: Is that currently how gvmd works?**

**A:** Yes! gvmd has NEVER sent actual VT code to scanners. It always sends:
- VT OID list (references)
- Preferences
- Target configuration

The scanner (openvassd or agent) must have the NVT feed locally.

**Q: Does it send those kind of instructions to the agent controller through the POST?**

**A:** Yes! The `POST /scans` request contains:
- VT OIDs (which tests to run)
- VT preferences (how to configure each test)
- Scanner preferences (global settings)
- Target info (what to scan)
- Agent IDs (which agents should execute)

**All proven by source code evidence in src/manage.c:7358-7499.**

---

## Implementation Guidance

### To Build Agent-Based Scanning:

1. **Start with OpenVAS scanner code**
   - Fork `openvassd` scanner daemon
   - Strip out OSP protocol (replace with polling logic)
   - Add heartbeat/job polling
   - Add result submission

2. **Add NVT feed sync**
   - Implement rsync client or HTTP downloader
   - Build OID → filename index
   - Verify GPG signatures

3. **Build Agent Controller service**
   - Implement Scanner API (receive scans from gvmd)
   - Implement Admin API (agent management)
   - Implement Agent-Facing API (job queue)
   - Build job queue system
   - Build result aggregation

4. **Test with real VTs**
   - Download Greenbone Community Feed
   - Test with simple VTs first (service detection)
   - Validate results match OpenVAS format
   - Test with complex VTs (authenticated checks)

The agent is NOT a lightweight runner - it's a **full-fledged vulnerability scanner** that happens to poll for work instead of listening for connections.
