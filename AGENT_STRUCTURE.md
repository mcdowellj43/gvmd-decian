# GVMD Backend Agent Infrastructure Documentation

## Overview
The Greenbone Vulnerability Manager Daemon (GVMD) backend implements a comprehensive agent management system that handles distributed scanning agents, their configuration, monitoring, and binary distribution. The system is built in C and provides the core backend functionality for agent operations.

## Architecture Components

### 1. Core Data Structures (`src/manage_agents.h`)

#### Agent Data Structure
The `agent_data` structure represents a complete agent entity:

```c
struct agent_data {
    agent_t row_id;                                    // Database row ID
    gchar *uuid;                                       // Unique identifier
    gchar *name;                                       // Display name
    gchar *agent_id;                                   // Agent identifier
    gchar *hostname;                                   // Host system name
    int authorized;                                    // Authorization status
    gchar *connection_status;                          // Current connection state
    agent_ip_data_list_t ip_addresses;                // IP address list
    int ip_address_count;                              // Number of IPs
    time_t creation_time;                              // Creation timestamp
    time_t modification_time;                          // Last modification
    time_t last_update_agent_control;                 // Last control update
    time_t last_updater_heartbeat;                    // Last heartbeat
    agent_controller_scan_agent_config_t config;      // Agent configuration
    gchar *comment;                                    // Administrative comment
    user_t owner;                                      // Owner user
    scanner_t scanner;                                 // Associated scanner
    gchar *updater_version;                           // Updater version
    gchar *agent_version;                             // Agent version
    gchar *operating_system;                          // OS information
    gchar *architecture;                              // System architecture
    int update_to_latest;                             // Auto-update flag
};
```

#### Agent IP Management
```c
struct agent_ip_data {
    gchar *ip_address;
};

struct agent_ip_data_list {
    int count;
    agent_ip_data_t *items;
};
```

#### Agent Lists and Collections
```c
struct agent_data_list {
    int count;            // Number of agents in the list
    agent_data_t *agents; // Array of pointers to agents
};
```

### 2. Agent Controller Integration (`src/manage_agent_common.h`)

#### GVMD Agent Connector
```c
struct gvmd_agent_connector {
    agent_controller_connector_t base; // Original gvm-libs connector
    scanner_t scanner_id;              // GVMD-specific scanner id
};
```

This structure bridges the GVMD database layer with the agent controller communication layer.

#### Agent UUID Management
```c
struct agent_uuid_list {
    int count;           // Number of UUIDs in the list
    gchar **agent_uuids; // Array of UUID strings
};
```

### 3. Database Layer (`src/manage_sql_agents.h`)

#### Agent Iterator Columns
The system defines comprehensive database columns for agent iteration:

```c
#define AGENT_ITERATOR_COLUMNS \
{
    GET_ITERATOR_COLUMNS (agents),
    {"agent_id", NULL, KEYWORD_TYPE_STRING},
    {"hostname", NULL, KEYWORD_TYPE_STRING},
    {"authorized", NULL, KEYWORD_TYPE_INTEGER},
    {"connection_status", NULL, KEYWORD_TYPE_STRING},
    {"last_update", NULL, KEYWORD_TYPE_INTEGER},
    {"last_updater_heartbeat", NULL, KEYWORD_TYPE_INTEGER},
    {"config", NULL, KEYWORD_TYPE_STRING},
    {"scanner", NULL, KEYWORD_TYPE_INTEGER},
    {"updater_version", NULL, KEYWORD_TYPE_STRING},
    {"agent_version", NULL, KEYWORD_TYPE_STRING},
    {"operating_system", NULL, KEYWORD_TYPE_STRING},
    {"architecture", NULL, KEYWORD_TYPE_STRING},
    {"update_to_latest", NULL, KEYWORD_TYPE_INTEGER},
    {NULL, NULL, KEYWORD_TYPE_UNKNOWN}
}
```

### 4. GMP Protocol Layer (`src/gmp_agents.c`)

#### Command Structures
The GMP (Greenbone Management Protocol) layer provides XML-based communication:

- **get_agents_t**: Structure for handling `<get_agents>` commands
- **modify_agent_data_t**: Context for `<modify_agent>` operations
- **delete_agent_data_t**: Context for `<delete_agent>` operations

#### Response Codes
```c
typedef enum {
    AGENT_RESPONSE_SUCCESS = 0,
    AGENT_RESPONSE_NO_AGENTS_PROVIDED = -1,
    AGENT_RESPONSE_SCANNER_LOOKUP_FAILED = -2,
    AGENT_RESPONSE_AGENT_SCANNER_MISMATCH = -3,
    AGENT_RESPONSE_CONNECTOR_CREATION_FAILED = -4,
    AGENT_RESPONSE_CONTROLLER_UPDATE_FAILED = -5,
    AGENT_RESPONSE_CONTROLLER_DELETE_FAILED = -6,
    AGENT_RESPONSE_SYNC_FAILED = -7,
    AGENT_RESPONSE_INVALID_ARGUMENT = -8,
    AGENT_RESPONSE_INVALID_AGENT_OWNER = -9,
} agent_response_t;
```

## Agent Installer Infrastructure

### 1. Installer Data Structure (`src/manage_agent_installers.h`)

```c
typedef struct {
    agent_installer_t row_id;      // Database ID
    gchar *uuid;                   // Unique identifier
    gchar *name;                   // Installer name
    gchar *description;            // Description text
    gchar *content_type;           // MIME type
    gchar *file_extension;         // File extension
    gchar *installer_path;         // Path to installer file
    gchar *version;                // Version information
    gchar *checksum;               // File integrity checksum
    time_t creation_time;          // Creation timestamp
    time_t modification_time;      // Last modification
} agent_installer_data_t;
```

### 2. Binary Management

#### Feed Directory Structure
- **Base Directory**: `GVMD_FEED_DIR/agent-installers/`
- **Installer Files**: Binary executables and packages stored in organized directory structure
- **Metadata**: JSON metadata files describing available installers

#### File Operations
```c
// Open installer binary file with security validation
FILE *open_agent_installer_file(const char *installer_path, gchar **message);

// Validate installer file integrity and format
gboolean agent_installer_stream_is_valid(FILE *stream,
                                        gvm_stream_validator_t validator,
                                        gchar **message);

// File-based validation wrapper
gboolean agent_installer_file_is_valid(const char *path,
                                      const char *content_type,
                                      gchar **message);
```

#### Security Features
- **Path Validation**: Ensures installer paths remain within feed directory
- **Canonical Path Resolution**: Prevents directory traversal attacks
- **Stream Validation**: Validates binary content using configurable validators
- **Checksum Verification**: Integrity checking for downloaded binaries

### 3. Installer Synchronization

#### Feed Management
```c
// Check if agent installers should be synced with feed
gboolean should_sync_agent_installers();

// Synchronize installers from external feed
void manage_sync_agent_installers();

// Get last update time from metadata
time_t get_meta_agent_installers_last_update();

// Update last sync timestamp
void update_meta_agent_installers_last_update();
```

#### Binary Distribution Process
1. **Feed Synchronization**: Download installer binaries from official feed
2. **Validation**: Check file integrity and format compatibility
3. **Database Storage**: Store metadata and file paths in database
4. **Version Management**: Track installer versions and updates
5. **Distribution**: Serve binaries to agents via GMP protocol

### 4. Installer Types and Formats

#### Supported Platforms
The system supports multiple installer formats:
- **Windows**: `.exe`, `.msi` executables
- **Linux**: `.deb`, `.rpm`, `.tar.gz` packages
- **MacOS**: `.dmg`, `.pkg` installers
- **Generic**: Shell scripts and platform-neutral packages

#### Content Types
- `application/octet-stream`: Generic binary files
- `application/x-msi`: Windows MSI packages
- `application/x-debian-package`: Debian packages
- `application/x-rpm`: RPM packages
- `application/x-tar`: Compressed archives

### 5. Binary Buffer Management

#### Buffer Size Definitions
```c
#define AGENT_INSTALLER_READ_BUFFER_SIZE 4096
#define AGENT_INSTALLER_BASE64_BUFFER_SIZE ((AGENT_INSTALLER_READ_BUFFER_SIZE / 3 + 2) * 4)
#define AGENT_INSTALLER_BASE64_WITH_BREAKS_BUFFER_SIZE \
    (AGENT_INSTALLER_BASE64_BUFFER_SIZE + AGENT_INSTALLER_BASE64_BUFFER_SIZE / 76 + 1)
```

#### Binary Encoding
- **Base64 Encoding**: For transmission over XML/GMP protocol
- **Chunked Reading**: Efficient handling of large installer files
- **Memory Management**: Proper buffer allocation and cleanup

## Key Features

### Agent Lifecycle Management
1. **Registration**: Agents connect and register with unique identifiers
2. **Authorization**: Administrative approval process for new agents
3. **Configuration**: Set execution parameters, schedules, and policies
4. **Monitoring**: Continuous health monitoring via heartbeats
5. **Updates**: Automated agent software updates via installer system
6. **Decommission**: Clean removal of agents and associated data

### Security Architecture
- **Authorization Control**: Multi-level authorization system
- **Secure Communication**: Encrypted agent-server communication
- **Identity Verification**: Strong agent identity verification
- **Access Control**: Role-based access to agent management
- **Binary Integrity**: Cryptographic verification of installer binaries

### Scalability Features
- **Bulk Operations**: Efficient mass agent management
- **Database Optimization**: Indexed queries and efficient data structures
- **Connection Pooling**: Optimized agent controller connections
- **Feed Distribution**: Scalable binary distribution system

## Integration Points

### Scanner Integration
- **Scanner Association**: Each agent links to specific scanner configurations
- **Task Distribution**: Intelligent task assignment based on agent capabilities
- **Result Collection**: Centralized result aggregation from distributed agents

### Database Integration
- **SQL Layer**: Comprehensive database abstraction for agent data
- **Transaction Management**: ACID compliance for agent operations
- **Query Optimization**: Efficient filtering and iteration mechanisms
- **Data Integrity**: Foreign key constraints and referential integrity

### External Systems
- **Feed Synchronization**: Integration with Greenbone feed infrastructure
- **Agent Controller**: Communication with gvm-libs agent controller
- **File System**: Secure file management for installer binaries
- **Logging System**: Comprehensive audit trail for agent operations

## Development Notes

### Compilation Features
- **Conditional Compilation**: `ENABLE_AGENTS` flag for agent functionality
- **Memory Management**: Comprehensive allocation tracking and cleanup
- **Error Handling**: Robust error propagation and logging
- **Thread Safety**: Multi-threaded operation support

### Performance Considerations
- **Memory Efficiency**: Optimized data structures for large agent counts
- **I/O Optimization**: Buffered file operations for binary handling
- **Database Efficiency**: Prepared statements and connection reuse
- **Network Optimization**: Efficient binary distribution protocols

This comprehensive backend infrastructure provides enterprise-grade agent management capabilities with strong security, scalability, and reliability features.