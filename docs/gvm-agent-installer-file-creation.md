 │ # GVM Agent Installer Setup Guide                                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ **Version:** 1.0                                                                                                                          │ │
│ │ **Date:** 2025-11-13                                                                                                                      │ │
│ │ **Author:** System Documentation                                                                                                          │ │
│ │                                                                                                                                           │ │
│ │ ## Overview                                                                                                                               │ │
│ │                                                                                                                                           │ │
│ │ This guide documents the complete process for creating, configuring, and deploying GVM Agent installer files into a Greenbone             │ │
│ │ Vulnerability Management (GVM) environment. Agent installers allow administrators to deploy GVM agents to endpoints through the GSA web   │ │
│ │ interface.                                                                                                                                │ │
│ │                                                                                                                                           │ │
│ │ ## Prerequisites                                                                                                                          │ │
│ │                                                                                                                                           │ │
│ │ - Running GVM environment with gvmd container                                                                                             │ │
│ │ - Administrative access to the GVM containers                                                                                             │ │
│ │ - PostgreSQL database with proper schema (including `agent_installers` table)                                                             │ │
│ │ - Agent binary files (.deb, .rpm, .exe, etc.)                                                                                             │ │
│ │                                                                                                                                           │ │
│ │ ## Architecture Overview                                                                                                                  │ │
│ │                                                                                                                                           │ │
│ │ ```                                                                                                                                       │ │
│ │ ┌─────────────────────────────────────────────────────────────────┐                                                                       │ │
│ │ │                     GVM Feed Directory                          │                                                                       │ │
│ │ │  /var/lib/gvm/data-objects/gvmd/agent-installers/              │                                                                        │ │
│ │ │                                                                 │                                                                       │ │
│ │ │  ├── agent-installers.json          (metadata file)            │                                                                        │ │
│ │ │  ├── gvm-agent-2.0.0-Linux.deb     (installer binary)         │                                                                         │ │
│ │ │  ├── gvm-agent-2.0.0-Linux.rpm     (installer binary)         │                                                                         │ │
│ │ │  └── gvm-agent-2.0.0-windows.exe   (installer binary)         │                                                                         │ │
│ │ └─────────────────────────────────────────────────────────────────┘                                                                       │ │
│ │                               │                                                                                                           │ │
│ │                               │ Automatic Feed Sync                                                                                       │ │
│ │                               ▼                                                                                                           │ │
│ │ ┌─────────────────────────────────────────────────────────────────┐                                                                       │ │
│ │ │                    PostgreSQL Database                          │                                                                       │ │
│ │ │                                                                 │                                                                       │ │
│ │ │  agent_installers table:                                       │                                                                        │ │
│ │ │  ├── uuid, name, version                                       │                                                                        │ │
│ │ │  ├── description, content_type                                 │                                                                        │ │
│ │ │  ├── installer_path, checksum                                  │                                                                        │ │
│ │ │  └── creation_time, last_update                                │                                                                        │ │
│ │ └─────────────────────────────────────────────────────────────────┘                                                                       │ │
│ │                               │                                                                                                           │ │
│ │                               │ API Access                                                                                                │ │
│ │                               ▼                                                                                                           │ │
│ │ ┌─────────────────────────────────────────────────────────────────┐                                                                       │ │
│ │ │                      GSA Web Interface                          │                                                                       │ │
│ │ │                (Agent Installer Downloads)                      │                                                                       │ │
│ │ └─────────────────────────────────────────────────────────────────┘                                                                       │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ## Step-by-Step Process                                                                                                                   │ │
│ │                                                                                                                                           │ │
│ │ ### Step 1: Prepare the Feed Directory                                                                                                    │ │
│ │                                                                                                                                           │ │
│ │ Create the required directory structure with proper permissions:                                                                          │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Create directory structure                                                                                                              │ │
│ │ sudo mkdir -p /var/lib/gvm/data-objects/gvmd/agent-installers                                                                             │ │
│ │                                                                                                                                           │ │
│ │ # Set correct ownership (gvmd user varies by installation)                                                                                │ │
│ │ sudo chown -R gvmd:gvmd /var/lib/gvm/data-objects/gvmd/agent-installers                                                                   │ │
│ │                                                                                                                                           │ │
│ │ # Set appropriate permissions                                                                                                             │ │
│ │ chmod 755 /var/lib/gvm/data-objects/gvmd/agent-installers                                                                                 │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **For Docker environments:**                                                                                                              │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Check container name                                                                                                                    │ │
│ │ docker ps | grep gvmd                                                                                                                     │ │
│ │                                                                                                                                           │ │
│ │ # Access container and create directory                                                                                                   │ │
│ │ docker exec -it greenbone-community-edition-gvmd-1 bash                                                                                   │ │
│ │ mkdir -p /var/lib/gvm/data-objects/gvmd/agent-installers                                                                                  │ │
│ │ chown gvmd:gvmd /var/lib/gvm/data-objects/gvmd/agent-installers                                                                           │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 2: Create Initial Metadata File                                                                                                  │ │
│ │                                                                                                                                           │ │
│ │ Create the base JSON metadata file:                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ cat > /var/lib/gvm/data-objects/gvmd/agent-installers/agent-installers.json << 'EOF'                                                      │ │
│ │ {                                                                                                                                         │ │
│ │   "installers": []                                                                                                                        │ │
│ │ }                                                                                                                                         │ │
│ │ EOF                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ chown gvmd:gvmd /var/lib/gvm/data-objects/gvmd/agent-installers/agent-installers.json                                                     │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 3: Add Agent Installer Files                                                                                                     │ │
│ │                                                                                                                                           │ │
│ │ Copy your compiled agent installer(s) to the feed directory:                                                                              │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Copy installer binary to feed directory                                                                                                 │ │
│ │ sudo cp gvm-agent-2.0.0-Linux.deb /var/lib/gvm/data-objects/gvmd/agent-installers/                                                        │ │
│ │                                                                                                                                           │ │
│ │ # Set correct ownership and permissions                                                                                                   │ │
│ │ sudo chown gvmd:gvmd /var/lib/gvm/data-objects/gvmd/agent-installers/gvm-agent-2.0.0-Linux.deb                                            │ │
│ │ chmod 644 /var/lib/gvm/data-objects/gvmd/agent-installers/gvm-agent-2.0.0-Linux.deb                                                       │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 4: Calculate File Checksum                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ Generate SHA256 checksum for integrity verification:                                                                                      │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ cd /var/lib/gvm/data-objects/gvmd/agent-installers                                                                                        │ │
│ │ sha256sum gvm-agent-2.0.0-Linux.deb                                                                                                       │ │
│ │ # Output: a73924fdbb9d55711fc68a5aa65b830c6827d77e76d65dba6c396b319f00f743  gvm-agent-2.0.0-Linux.deb                                     │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 5: Generate UUID                                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ Create a unique identifier for the installer:                                                                                             │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Using Python                                                                                                                            │ │
│ │ python3 -c "import uuid; print(uuid.uuid4())"                                                                                             │ │
│ │ # Output: 9ff07a74-cb7e-4405-8ed0-04d64f67ec29                                                                                            │ │
│ │                                                                                                                                           │ │
│ │ # Using uuidgen (if available)                                                                                                            │ │
│ │ uuidgen                                                                                                                                   │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 6: Update Metadata JSON                                                                                                          │ │
│ │                                                                                                                                           │ │
│ │ Add the installer entry to the JSON file:                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ ```json                                                                                                                                   │ │
│ │ {                                                                                                                                         │ │
│ │   "installers": [                                                                                                                         │ │
│ │     {                                                                                                                                     │ │
│ │       "uuid": "9ff07a74-cb7e-4405-8ed0-04d64f67ec29",                                                                                     │ │
│ │       "name": "GVM Agent - Linux (Debian/Ubuntu)",                                                                                        │ │
│ │       "description": "Greenbone Vulnerability Management Agent for Debian and Ubuntu Linux systems",                                      │ │
│ │       "contentType": "application/vnd.debian.binary-package",                                                                             │ │
│ │       "fileExtension": "deb",                                                                                                             │ │
│ │       "installerPath": "gvm-agent-2.0.0-Linux.deb",                                                                                       │ │
│ │       "version": "2.0.0",                                                                                                                 │ │
│ │       "checksum": "sha256:a73924fdbb9d55711fc68a5aa65b830c6827d77e76d65dba6c396b319f00f743",                                              │ │
│ │       "created": "2025-11-13T13:00:00Z",                                                                                                  │ │
│ │       "lastModified": "2025-11-13T18:40:00Z"                                                                                              │ │
│ │     }                                                                                                                                     │ │
│ │   ]                                                                                                                                       │ │
│ │ }                                                                                                                                         │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 7: Trigger Feed Synchronization                                                                                                  │ │
│ │                                                                                                                                           │ │
│ │ Update the file timestamp to trigger automatic import:                                                                                    │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Touch the metadata file to update modification time                                                                                     │ │
│ │ touch /var/lib/gvm/data-objects/gvmd/agent-installers/agent-installers.json                                                               │ │
│ │                                                                                                                                           │ │
│ │ # Restart gvmd to trigger feed sync                                                                                                       │ │
│ │ docker restart greenbone-community-edition-gvmd-1                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ # Or restart gvmd service (non-Docker)                                                                                                    │ │
│ │ sudo systemctl restart gvmd                                                                                                               │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ### Step 8: Verification                                                                                                                  │ │
│ │                                                                                                                                           │ │
│ │ Verify the installer was imported successfully:                                                                                           │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Check database directly                                                                                                                 │ │
│ │ docker exec greenbone-community-edition-pg-gvm-1 psql -U gvmd -d gvmd -c \                                                                │ │
│ │   "SELECT uuid, name, version, installer_path FROM agent_installers;"                                                                     │ │
│ │                                                                                                                                           │ │
│ │ # Expected output:                                                                                                                        │ │
│ │ #                  uuid                 |               name                | version |      installer_path                               │ │
│ │ # --------------------------------------+-----------------------------------+---------+---------------------------                        │ │
│ │ #  9ff07a74-cb7e-4405-8ed0-04d64f67ec29 | GVM Agent - Linux (Debian/Ubuntu) | 2.0.0   | gvm-agent-2.0.0-Linux.deb                         │ │
│ │                                                                                                                                           │ │
│ │ # Check via GMP protocol (if available)                                                                                                   │ │
│ │ gvm-cli socket --socketpath /var/run/gvmd/gvmd.sock --xml "<get_agent_installers/>"                                                       │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ## Required Database Schema                                                                                                               │ │
│ │                                                                                                                                           │ │
│ │ The `agent_installers` table must have the following structure:                                                                           │ │
│ │                                                                                                                                           │ │
│ │ ```sql                                                                                                                                    │ │
│ │ CREATE TABLE agent_installers (                                                                                                           │ │
│ │     id INTEGER PRIMARY KEY,                                                                                                               │ │
│ │     uuid TEXT NOT NULL UNIQUE,                                                                                                            │ │
│ │     name TEXT NOT NULL,                                                                                                                   │ │
│ │     owner INTEGER REFERENCES users(id),                                                                                                   │ │
│ │     creation_time INTEGER,                                                                                                                │ │
│ │     modification_time INTEGER,                                                                                                            │ │
│ │     description TEXT,                                                                                                                     │ │
│ │     content_type TEXT,                                                                                                                    │ │
│ │     file_extension TEXT,                                                                                                                  │ │
│ │     installer_path TEXT,  -- Relative path to binary file                                                                                 │ │
│ │     version TEXT,                                                                                                                         │ │
│ │     checksum TEXT,                                                                                                                        │ │
│ │     last_update INTEGER   -- Critical: Required for feed sync                                                                             │ │
│ │ );                                                                                                                                        │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **⚠️ Important:** If the `last_update` column is missing, add it:                                                                         │ │
│ │ ```sql                                                                                                                                    │ │
│ │ ALTER TABLE agent_installers ADD COLUMN last_update INTEGER;                                                                              │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ## JSON Metadata Format Specification                                                                                                     │ │
│ │                                                                                                                                           │ │
│ │ ### Required Fields                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ | Field | Type | Description | Example |                                                                                                  │ │
│ │ |-------|------|-------------|---------|                                                                                                  │ │
│ │ | `uuid` | string | Unique identifier (RFC 4122) | `"9ff07a74-cb7e-4405-8ed0-04d64f67ec29"` |                                             │ │
│ │ | `name` | string | Display name for installer | `"GVM Agent - Linux (Debian/Ubuntu)"` |                                                  │ │
│ │ | `installerPath` | string | Relative path to binary file | `"gvm-agent-2.0.0-Linux.deb"` |                                               │ │
│ │ | `version` | string | Installer version | `"2.0.0"` |                                                                                    │ │
│ │ | `checksum` | string | SHA256 hash with prefix | `"sha256:a73924fdbb9..."` |                                                             │ │
│ │                                                                                                                                           │ │
│ │ ### Optional Fields                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ | Field | Type | Description | Example |                                                                                                  │ │
│ │ |-------|------|-------------|---------|                                                                                                  │ │
│ │ | `description` | string | Detailed description | `"Agent for vulnerability scanning"` |                                                  │ │
│ │ | `contentType` | string | MIME type | `"application/vnd.debian.binary-package"` |                                                        │ │
│ │ | `fileExtension` | string | File extension | `"deb"` |                                                                                   │ │
│ │ | `created` | string | Creation timestamp (ISO 8601) | `"2025-11-13T13:00:00Z"` |                                                         │ │
│ │ | `lastModified` | string | Last modification timestamp | `"2025-11-13T18:40:00Z"` |                                                      │ │
│ │                                                                                                                                           │ │
│ │ ### Content Type Examples                                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ | Installer Type | Content Type | File Extension |                                                                                        │ │
│ │ |----------------|--------------|----------------|                                                                                        │ │
│ │ | Debian Package | `application/vnd.debian.binary-package` | `deb` |                                                                      │ │
│ │ | RPM Package | `application/x-rpm` | `rpm` |                                                                                             │ │
│ │ | Windows Executable | `application/vnd.microsoft.portable-executable` | `exe` |                                                          │ │
│ │ | MSI Package | `application/x-msi` | `msi` |                                                                                             │ │
│ │ | macOS Package | `application/x-apple-diskimage` | `pkg` |                                                                               │ │
│ │ | Generic Binary | `application/octet-stream` | `""` |                                                                                    │ │
│ │                                                                                                                                           │ │
│ │ ## Multi-Platform Example                                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ Complete example with multiple installers:                                                                                                │ │
│ │                                                                                                                                           │ │
│ │ ```json                                                                                                                                   │ │
│ │ {                                                                                                                                         │ │
│ │   "installers": [                                                                                                                         │ │
│ │     {                                                                                                                                     │ │
│ │       "uuid": "linux-debian-uuid-here",                                                                                                   │ │
│ │       "name": "GVM Agent - Linux (Debian/Ubuntu)",                                                                                        │ │
│ │       "description": "GVM Agent for Debian and Ubuntu systems",                                                                           │ │
│ │       "contentType": "application/vnd.debian.binary-package",                                                                             │ │
│ │       "fileExtension": "deb",                                                                                                             │ │
│ │       "installerPath": "gvm-agent-2.0.0-linux-amd64.deb",                                                                                 │ │
│ │       "version": "2.0.0",                                                                                                                 │ │
│ │       "checksum": "sha256:deb_checksum_here",                                                                                             │ │
│ │       "created": "2025-11-13T10:00:00Z",                                                                                                  │ │
│ │       "lastModified": "2025-11-13T10:00:00Z"                                                                                              │ │
│ │     },                                                                                                                                    │ │
│ │     {                                                                                                                                     │ │
│ │       "uuid": "linux-rpm-uuid-here",                                                                                                      │ │
│ │       "name": "GVM Agent - Linux (RHEL/CentOS)",                                                                                          │ │
│ │       "description": "GVM Agent for RHEL and CentOS systems",                                                                             │ │
│ │       "contentType": "application/x-rpm",                                                                                                 │ │
│ │       "fileExtension": "rpm",                                                                                                             │ │
│ │       "installerPath": "gvm-agent-2.0.0-linux-amd64.rpm",                                                                                 │ │
│ │       "version": "2.0.0",                                                                                                                 │ │
│ │       "checksum": "sha256:rpm_checksum_here",                                                                                             │ │
│ │       "created": "2025-11-13T10:00:00Z",                                                                                                  │ │
│ │       "lastModified": "2025-11-13T10:00:00Z"                                                                                              │ │
│ │     },                                                                                                                                    │ │
│ │     {                                                                                                                                     │ │
│ │       "uuid": "windows-exe-uuid-here",                                                                                                    │ │
│ │       "name": "GVM Agent - Windows",                                                                                                      │ │
│ │       "description": "GVM Agent for Windows systems",                                                                                     │ │
│ │       "contentType": "application/vnd.microsoft.portable-executable",                                                                     │ │
│ │       "fileExtension": "exe",                                                                                                             │ │
│ │       "installerPath": "gvm-agent-2.0.0-windows-amd64.exe",                                                                               │ │
│ │       "version": "2.0.0",                                                                                                                 │ │
│ │       "checksum": "sha256:exe_checksum_here",                                                                                             │ │
│ │       "created": "2025-11-13T10:00:00Z",                                                                                                  │ │
│ │       "lastModified": "2025-11-13T10:00:00Z"                                                                                              │ │
│ │     }                                                                                                                                     │ │
│ │   ]                                                                                                                                       │ │
│ │ }                                                                                                                                         │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ## Automatic Feed Synchronization Process                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ ### How It Works                                                                                                                          │ │
│ │                                                                                                                                           │ │
│ │ The GVM feed synchronization process (`src/manage.c:4235`) automatically imports agent installers:                                        │ │
│ │                                                                                                                                           │ │
│ │ 1. **Trigger Detection**: gvmd checks if `agent-installers.json` modification time > database `last_update`                               │ │
│ │ 2. **JSON Parsing**: Parses the metadata file and extracts installer entries                                                              │ │
│ │ 3. **Database Operations**:                                                                                                               │ │
│ │    - New installers → `INSERT INTO agent_installers`                                                                                      │ │
│ │    - Existing installers → `UPDATE agent_installers` (if modified)                                                                        │ │
│ │ 4. **Timestamp Update**: Updates `meta.agent_installers_last_update`                                                                      │ │
│ │                                                                                                                                           │ │
│ │ ### Sync Triggers                                                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ - **Startup**: gvmd startup automatically checks for feed updates                                                                         │ │
│ │ - **Periodic**: Regular checks during operation                                                                                           │ │
│ │ - **Manual**: File modification time change triggers sync on next check                                                                   │ │
│ │ - **Restart**: Container/service restart forces immediate sync check                                                                      │ │
│ │                                                                                                                                           │ │
│ │ ## Troubleshooting                                                                                                                        │ │
│ │                                                                                                                                           │ │
│ │ ### Common Issues                                                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ #### 1. Agent Installer Not Appearing in Database                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ **Symptoms:**                                                                                                                             │ │
│ │ ```sql                                                                                                                                    │ │
│ │ SELECT * FROM agent_installers;                                                                                                           │ │
│ │ -- Returns: (0 rows)                                                                                                                      │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **Solutions:**                                                                                                                            │ │
│ │ - Check database schema: `\d agent_installers` (ensure `last_update` column exists)                                                       │ │
│ │ - Verify file permissions: `ls -la /var/lib/gvm/data-objects/gvmd/agent-installers/`                                                      │ │
│ │ - Check JSON syntax: `cat agent-installers.json | python3 -m json.tool`                                                                   │ │
│ │ - Review gvmd logs: `docker logs greenbone-community-edition-gvmd-1 | grep -i installer`                                                  │ │
│ │                                                                                                                                           │ │
│ │ #### 2. SQL Errors About Missing Columns                                                                                                  │ │
│ │                                                                                                                                           │ │
│ │ **Symptoms:**                                                                                                                             │ │
│ │ ```                                                                                                                                       │ │
│ │ ERROR: column "last_update" does not exist                                                                                                │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **Solution:**                                                                                                                             │ │
│ │ ```sql                                                                                                                                    │ │
│ │ ALTER TABLE agent_installers ADD COLUMN last_update INTEGER;                                                                              │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ #### 3. Permission Denied Errors                                                                                                          │ │
│ │                                                                                                                                           │ │
│ │ **Symptoms:**                                                                                                                             │ │
│ │ ```                                                                                                                                       │ │
│ │ Permission denied: /var/lib/gvm/data-objects/gvmd/agent-installers/                                                                       │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **Solution:**                                                                                                                             │ │
│ │ ```bash                                                                                                                                   │ │
│ │ chown -R gvmd:gvmd /var/lib/gvm/data-objects/gvmd/agent-installers/                                                                       │ │
│ │ chmod 755 /var/lib/gvm/data-objects/gvmd/agent-installers/                                                                                │ │
│ │ chmod 644 /var/lib/gvm/data-objects/gvmd/agent-installers/*                                                                               │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ #### 4. JSON Parsing Errors                                                                                                               │ │
│ │                                                                                                                                           │ │
│ │ **Symptoms:**                                                                                                                             │ │
│ │ ```                                                                                                                                       │ │
│ │ libgvm util:WARNING: End error: Error on line 1 char 1: Document was empty                                                                │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **Solution:**                                                                                                                             │ │
│ │ - Validate JSON syntax: `python3 -c "import json; print(json.load(open('agent-installers.json')))"`                                       │ │
│ │ - Check file encoding (should be UTF-8)                                                                                                   │ │
│ │ - Ensure proper field names (see JSON format specification)                                                                               │ │
│ │                                                                                                                                           │ │
│ │ ### Verification Commands                                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ ```bash                                                                                                                                   │ │
│ │ # Check file structure                                                                                                                    │ │
│ │ ls -la /var/lib/gvm/data-objects/gvmd/agent-installers/                                                                                   │ │
│ │                                                                                                                                           │ │
│ │ # Validate JSON                                                                                                                           │ │
│ │ cat /var/lib/gvm/data-objects/gvmd/agent-installers/agent-installers.json | python3 -m json.tool                                          │ │
│ │                                                                                                                                           │ │
│ │ # Check database import                                                                                                                   │ │
│ │ docker exec greenbone-community-edition-pg-gvm-1 psql -U gvmd -d gvmd -c \                                                                │ │
│ │   "SELECT uuid, name, version, checksum FROM agent_installers;"                                                                           │ │
│ │                                                                                                                                           │ │
│ │ # Monitor gvmd logs                                                                                                                       │ │
│ │ docker logs greenbone-community-edition-gvmd-1 --follow                                                                                   │ │
│ │ ```                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ ## Security Considerations                                                                                                                │ │
│ │                                                                                                                                           │ │
│ │ ### File Security                                                                                                                         │ │
│ │ - Store installer files with read-only permissions (`644`)                                                                                │ │
│ │ - Use strong SHA256 checksums for integrity verification                                                                                  │ │
│ │ - Validate UUIDs to prevent conflicts                                                                                                     │ │
│ │ - Restrict directory permissions to gvmd user only                                                                                        │ │
│ │                                                                                                                                           │ │
│ │ ### Path Security                                                                                                                         │ │
│ │ - Installer paths are relative to feed directory (prevents directory traversal)                                                           │ │
│ │ - GVM validates paths before file access (`open_agent_installer_file()`)                                                                  │ │
│ │ - No execution of installer files on GVM server (download only)                                                                           │ │
│ │                                                                                                                                           │ │
│ │ ### Access Control                                                                                                                        │ │
│ │ - Agent installer access controlled by GVM permissions system                                                                             │ │
│ │ - Feed import requires appropriate user roles                                                                                             │ │
│ │ - Database access restricted to gvmd user                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ ## Best Practices                                                                                                                         │ │
│ │                                                                                                                                           │ │
│ │ 1. **Version Management**: Use semantic versioning (e.g., "2.0.0")                                                                        │ │
│ │ 2. **UUID Generation**: Always generate new UUIDs for new installers                                                                      │ │
│ │ 3. **Checksum Verification**: Always include SHA256 checksums                                                                             │ │
│ │ 4. **File Naming**: Use descriptive, version-specific filenames                                                                           │ │
│ │ 5. **Testing**: Verify imports in development before production deployment                                                                │ │
│ │ 6. **Backup**: Backup existing `agent-installers.json` before modifications                                                               │ │
│ │ 7. **Documentation**: Document installer requirements and compatibility                                                                   │ │
│ │                                                                                                                                           │ │
│ │ ## Support and References                                                                                                                 │ │
│ │                                                                                                                                           │ │
│ │ - **Database Schema**: `src/manage_sql_agent_installers.c`                                                                                │ │
│ │ - **Feed Sync Logic**: `src/manage_agent_installers.c`                                                                                    │ │
│ │ - **Main Orchestration**: `src/manage.c:4235`                                                                                             │ │
│ │ - **GMP Protocol**: `<get_agent_installers/>` command                                                                                     │ │
│ │ - **File Handling**: Path validation in `open_agent_installer_file()`                                                                     │ │
│ │                                                                                                                                           │ │
│ │ ---                                                                                                                                       │ │
│ │                                                                                                                                           │ │
│ │ **Note:** This process is specific to GVM environments with agent installer support. Ensure your GVM version includes the agent installer │ │
│ │  functionality before implementing this process. 
