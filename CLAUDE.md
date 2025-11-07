# Claude Code Notes

## Agent Controller Implementation

### Feasibility Analysis
- See `docs/AGENT_CONTROLLER_FEASIBILITY.md` for complete analysis of building an open-source Agent Controller service
- Building a compatible Agent Controller is feasible based on the client-side code in this repository
- The gvmd codebase contains all necessary API specifications and expected data structures

### Agent Controller Client Code Locations
The following files in `./src` contain client-side implementation that reveals the Agent Controller API:

**Core Integration Files:**
- `src/manage_agents.c` - Agent synchronization, CRUD operations, data transformation
- `src/manage_agents.h` - Agent data structures and function prototypes
- `src/manage_agent_common.c` - Connector builder, HTTP client configuration
- `src/manage_agent_common.h` - Common agent utilities and types

**GMP Command Handlers:**
- `src/gmp_agents.c` - GMP commands: get_agents, modify_agent, delete_agent
- `src/gmp_agents.h` - GMP agent command interfaces
- `src/gmp_agent_groups.c` - Agent group management commands
- `src/gmp_agent_groups.h` - Agent group interfaces
- `src/gmp_agent_installers.c` - Agent installer retrieval commands
- `src/gmp_agent_installers.h` - Agent installer interfaces
- `src/gmp_agent_control_scan_agent_config.c` - Scan configuration management
- `src/gmp_agent_control_scan_agent_config.h` - Scan config interfaces

**Database Layer:**
- `src/manage_sql_agents.c` - Agent database operations
- `src/manage_sql_agent_groups.c` - Agent group database operations
- `src/manage_sql_agent_installers.c` - Agent installer database operations

**Key Header (Outside Repo):**
- `/usr/include/gvm/agent_controller/agent_controller.h` - Complete API contract from gvm-libs

These files show exactly how gvmd expects to communicate with an Agent Controller service via HTTP/HTTPS REST API.
