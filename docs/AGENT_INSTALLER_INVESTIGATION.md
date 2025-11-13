# Agent Installer Support Investigation

## Executive Summary

The gvmd repository **already has full agent installer support implemented**, but it's disabled by default. The feature is controlled by the `ENABLE_AGENTS` CMake build flag and includes:

- Complete GMP commands (`get_agent_installers`, `get_agent_installer_file`)
- Database schema for storing installer metadata
- Feed synchronization from JSON metadata files
- File serving with checksum validation

## Build Configuration

### CMake Flag: ENABLE_AGENTS

**Location:** `CMakeLists.txt:258-273`

```cmake
if(NOT ENABLE_AGENTS)
  set(ENABLE_AGENTS 0)
endif(NOT ENABLE_AGENTS)
add_definitions(-DENABLE_AGENTS=${ENABLE_AGENTS})
```

### How to Enable

Build gvmd with the flag enabled:

```bash
cmake -DENABLE_AGENTS=1 ..
make
make install
```

### Dependencies

When `ENABLE_AGENTS=1`, the build requires:
- **libgvm_agent_controller >= 22.30** (`src/CMakeLists.txt:44-52`)

### Impact on GMP Version

The GMP protocol version changes based on this flag (`CMakeLists.txt:118-123`):
- `ENABLE_AGENTS=0`: GMP version **22.7**
- `ENABLE_AGENTS=1`: GMP version **22.8**

This allows clients to detect agent support by checking the GMP version.

## GMP Commands

### 1. get_agent_installers

**Handler:** `src/gmp_agent_installers.c:get_agent_installers_run()`

**Purpose:** Retrieve metadata about available agent installers

**XML Response Structure:**
```xml
<get_agent_installers_response status="200" status_text="OK">
  <agent_installer id="uuid">
    <owner><name>admin</name></owner>
    <name>Windows 11</name>
    <comment/>
    <creation_time>2025-04-11T13:30:00Z</creation_time>
    <modification_time>2025-04-11T13:32:00Z</modification_time>
    <writable>0</writable>
    <in_use>0</in_use>
    <permissions>...</permissions>
    <description>Greenbone Agent for Windows 11</description>
    <content_type>application/zip</content_type>
    <file_extension>zip</file_extension>
    <version>1.3.0</version>
    <checksum>sha256:3bbd04dd65dbb8b3f272bd8013d0d4b12fe54be30bb81f3e5df66306fe0fa0d3</checksum>
    <last_update>2025-05-06T11:12:57Z</last_update>
    <file_validity>valid</file_validity>
  </agent_installer>
</get_agent_installers_response>
```

**Supported Attributes:**
- `agent_installer_id`: UUID to get specific installer
- `filter`: Filter term to query installers
- `details`: Include file validity check

### 2. get_agent_installer_file

**Handler:** `src/gmp_agent_installers.c:get_agent_installer_file_run()`

**Purpose:** Download the actual installer file

**XML Response:**
```xml
<get_agent_installer_file_response status="200" status_text="OK">
  <file agent_installer_id="uuid">
    <name>Windows 11</name>
    <content_type>application/zip</content_type>
    <file_extension>zip</file_extension>
    <checksum>sha256:...</checksum>
    <content>BASE64_ENCODED_FILE_CONTENT</content>
  </file>
</get_agent_installer_file_response>
```

**Required Attribute:**
- `agent_installer_id`: UUID of installer to download

**Security Features:**
- Validates checksum during read
- Prevents path traversal attacks
- Ensures files are within feed directory

## Database Schema

### Table: agent_installers

**Creation:** `src/manage_pg.c:2810-2824`

```sql
CREATE TABLE IF NOT EXISTS agent_installers (
  id SERIAL PRIMARY KEY,
  uuid text UNIQUE NOT NULL,
  owner integer REFERENCES users (id) ON DELETE RESTRICT,
  name text NOT NULL,
  comment text,
  creation_time integer,
  modification_time integer,
  description text,
  content_type text,
  file_extension text,
  installer_path text,
  version text,
  checksum text,
  last_update integer
);
```

### Key Functions

**Database Operations:** `src/manage_sql_agent_installers.c`

- `create_agent_installer_from_data()` - Insert new installer metadata
- `update_agent_installer_from_data()` - Update existing installer
- `agent_installer_by_uuid()` - Find installer by UUID
- `init_agent_installer_iterator()` - Query installers with filtering

## File Storage

### Directory Structure

**Base Directory:** `GVMD_FEED_DIR/agent-installers/`

Default path: `/var/lib/gvm/data-objects/gvmd/agent-installers/`

**Functions:** `src/manage_agent_installers.c:232-256`

```c
const gchar *feed_dir_agent_installers()
{
  return g_build_filename(GVMD_FEED_DIR, "agent-installers", NULL);
}
```

### Metadata File

**Location:** `GVMD_FEED_DIR/agent-installers/agent-installers.json`

**Format:**
```json
{
  "installers": [
    {
      "uuid": "b993b6f5-f9fb-4e6e-9c94-dd46c00e058d",
      "name": "Windows 11",
      "description": "Greenbone Agent for Windows 11",
      "contentType": "application/zip",
      "fileExtension": "zip",
      "installerPath": "windows/greenbone-agent-1.3.0-win11.zip",
      "version": "1.3.0",
      "checksum": "sha256:3bbd04dd65dbb8b3f272bd8013d0d4b12fe54be30bb81f3e5df66306fe0fa0d3",
      "created": "2025-04-11T13:30:00Z",
      "lastModified": "2025-04-11T13:32:00Z"
    }
  ]
}
```

### File Validation

**Checksum Validation:** `src/manage_agent_installers.c:177-217`

- Uses `gvm_stream_validator` from gvm-libs
- Validates SHA256 checksums during read
- Prevents serving corrupted/tampered files

**Path Security:** `src/manage_agent_installers.c:58-106`

- Canonicalizes paths to prevent traversal
- Ensures files are within feed directory
- Returns error for invalid paths

## Feed Synchronization

### Auto-Sync Process

**Function:** `src/manage_agent_installers.c:525-601`

The feed sync runs automatically when:
1. The metadata file exists
2. The file modification time > database last update time

```c
gboolean should_sync_agent_installers()
{
  time_t db_last_update = get_meta_agent_installers_last_update();

  if (g_stat(feed_metadata_file_agent_installers(), &state))
    return FALSE;

  if (state.st_mtime >= db_last_update)
    return TRUE;

  return FALSE;
}
```

### Sync Process

1. **Parse JSON** metadata file
2. **Compare timestamps** between feed and database
3. **Create/Update** installers in database
4. **Set permissions** based on "Feed Import Roles" setting
5. **Update last sync time** in meta table

### Manual Sync

```c
void manage_sync_agent_installers()
{
  sync_agent_installers_with_feed(FALSE);
}
```

## How to Enable Agent Installer Support

### Step 1: Build with ENABLE_AGENTS

```bash
cd /path/to/gvmd/build
cmake -DENABLE_AGENTS=1 ..
make
sudo make install
```

### Step 2: Create Feed Directory Structure

```bash
sudo mkdir -p /var/lib/gvm/data-objects/gvmd/agent-installers
sudo chown gvm:gvm /var/lib/gvm/data-objects/gvmd/agent-installers
```

### Step 3: Create Metadata File

Create `/var/lib/gvm/data-objects/gvmd/agent-installers/agent-installers.json`:

```json
{
  "version": "1.0",
  "installers": []
}
```

### Step 4: Add Installer Files and Metadata

For each installer:

1. **Copy installer file** to feed directory:
   ```bash
   sudo cp greenbone-agent.exe /var/lib/gvm/data-objects/gvmd/agent-installers/
   ```

2. **Calculate checksum**:
   ```bash
   sha256sum greenbone-agent.exe
   # Output: abc123...def456
   ```

3. **Add entry to JSON**:
   ```json
   {
     "uuid": "unique-uuid-here",
     "name": "Windows Agent",
     "description": "Greenbone Agent for Windows",
     "contentType": "application/octet-stream",
     "fileExtension": "exe",
     "installerPath": "greenbone-agent.exe",
     "version": "1.0.0",
     "checksum": "sha256:abc123...def456",
     "created": "2025-11-11T10:00:00Z",
     "lastModified": "2025-11-11T10:00:00Z"
   }
   ```

### Step 5: Restart gvmd

```bash
sudo systemctl restart gvmd
```

The feed will auto-sync on next run.

### Step 6: Verify in Frontend

The GSA frontend should now:
1. Detect GMP version 22.8
2. Show agent installer UI
3. Poll `get_agent_installers` command
4. Allow downloading installers via `get_agent_installer_file`

## Permission System

### Feed Import Owner

The "Feed Import Owner" setting controls which user owns synced installers.

### Feed Import Roles

The "Feed Import Roles" setting (comma-separated role UUIDs) determines which roles get `get_agent_installers` permission.

**Permission Creation:** `src/manage_sql_agent_installers.c:84-123`

## Frontend Integration

The GSA frontend already supports this feature when it detects:
- **GMP version >= 22.8**
- **User has `get_agent_installers` permission**

The frontend will:
1. Poll for available installers
2. Display them in the UI
3. Allow users to download installer files

## Code Locations Reference

### GMP Handlers
- `src/gmp_agent_installers.c` - GMP command handlers
- `src/gmp_agent_installers.h` - GMP command headers

### Business Logic
- `src/manage_agent_installers.c` - Feed sync, file handling
- `src/manage_agent_installers.h` - Data structures

### Database Layer
- `src/manage_sql_agent_installers.c` - SQL operations
- `src/manage_sql_agent_installers.h` - SQL headers, schema macros

### Core Integration
- `src/gmp.c:88-92` - Include headers (if ENABLE_AGENTS)
- `src/gmp.c:5281-5289` - Command start handlers
- `src/gmp.c:21374-21382` - Command end handlers
- `src/manage_pg.c:2810-2824` - Table creation

### Build System
- `CMakeLists.txt:118-123` - GMP version selection
- `CMakeLists.txt:258-273` - ENABLE_AGENTS definition
- `src/CMakeLists.txt:44-52` - Dependency check
- `src/CMakeLists.txt:201-211` - Source file inclusion
- `src/CMakeLists.txt:245-253` - SQL source inclusion
- `src/CMakeLists.txt:276-285` - GMP source inclusion

### Schema
- `src/schema_formats/XML/GMP.xml.in` - GMP command documentation

## Summary

**The agent installer feature is ALREADY IMPLEMENTED** in gvmd. To make it available:

1. **Build:** Set `cmake -DENABLE_AGENTS=1`
2. **Create:** Feed directory `/var/lib/gvm/data-objects/gvmd/agent-installers/`
3. **Provide:** JSON metadata file `agent-installers.json`
4. **Add:** Installer files to the feed directory
5. **Sync:** Happens automatically when gvmd starts

The frontend will automatically detect and use this feature when GMP version is 22.8.
