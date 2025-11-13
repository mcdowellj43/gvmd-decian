#!/usr/bin/env python3
"""
Minimal Viable Agent Controller Service
Compatible with Greenbone gvmd agent-controller scanner type.

This service implements the REST API expected by gvm-libs agent_controller client.
Based on API specification from /usr/include/gvm/agent_controller/agent_controller.h

Phase 1 (Minimal Viable):
- GET /agents - Return list of agents (initially empty)
- GET /config - Return default scan agent configuration
- GET /installers - Return list of installers (initially empty)
- GET /agents?updates=true - Return agents with pending updates
- API key authentication

Usage:
    chmod +x agent-controller-service
    ./agent-controller-service

Then configure gvmd scanner:
    Scanner Type: agent-controller (type 7)
    Host: localhost
    Port: 3001
    Protocol: http
    API Key: test-api-key-12345
"""

from flask import Flask, request, jsonify
from functools import wraps
from datetime import datetime
import logging
import uuid

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_KEY = "test-api-key-12345"  # Change this in production
PORT = 3001
HOST = "0.0.0.0"

# In-memory storage (Phase 1 - will be replaced with SQLite in Phase 2)
agents = []
global_config = None
scans = {}  # Dictionary of scan_id -> scan data
scan_jobs = {}  # Dictionary of job_id -> job data
scan_results = {}  # Dictionary of scan_id -> list of results


def get_default_scan_agent_config():
    """
    Return default scan agent configuration matching the structure in
    agent_controller.h lines 66-117
    """
    return {
        "agent_control": {
            "retry": {
                "attempts": 5,
                "delay_in_seconds": 60,
                "max_jitter_in_seconds": 30
            }
        },
        "agent_script_executor": {
            "bulk_size": 10,
            "bulk_throttle_time_in_ms": 1000,
            "indexer_dir_depth": 5,
            "scheduler_cron_time": [
                "0 23 * * *"  # Daily at 11 PM
            ]
        },
        "heartbeat": {
            "interval_in_seconds": 600,
            "miss_until_inactive": 1
        }
    }


def error_response(code, message, details=None, status_code=400):
    """
    Generate standard error response per PRD Section 8.4

    Args:
        code: Error code (e.g., "INVALID_REQUEST", "NOT_FOUND")
        message: Human-readable error message
        details: List of detail dicts with 'field' and 'issue' keys
        status_code: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    request_id = f"req-{uuid.uuid4()}"
    error_obj = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id
        }
    }

    if details:
        error_obj["error"]["details"] = details

    logger.warning(f"Error response: {code} - {message} (request_id: {request_id})")
    return jsonify(error_obj), status_code


def require_api_key(f):
    """
    Decorator to require API key authentication.
    Expects X-API-KEY header. Per CLAUDE.md: NO FALLBACK BEHAVIOR.

    Per PRD Section 9.1 (SR-AUTH-001): All Admin API endpoints require API key authentication.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')

        if not api_key:
            logger.warning(f"Missing API key from {request.remote_addr}")
            return error_response(
                "UNAUTHORIZED",
                "Missing API key",
                details=[{"field": "X-API-KEY", "issue": "Required header is missing"}],
                status_code=401
            )

        if api_key != API_KEY:
            logger.warning(f"Invalid API key from {request.remote_addr}")
            return error_response(
                "UNAUTHORIZED",
                "Invalid API key",
                details=[{"field": "X-API-KEY", "issue": "API key is not valid"}],
                status_code=401
            )

        return f(*args, **kwargs)
    return decorated_function


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (no auth required)"""
    return jsonify({
        "status": "ok",
        "service": "agent-controller",
        "version": "0.1.0-mvp"
    })


# ============================================================================
# Scanner API - Endpoints for gvmd to interact with Agent Controller
# Per PRD Section 6.1 (FR-AC-001 to FR-AC-003)
# ============================================================================

@app.route('/scans', methods=['POST'])
def create_scan():
    """
    POST /scans - Create a new vulnerability scan

    Maps to: FR-AC-001 (Scanner API - Accept Scan Requests)

    Request body per PRD Section 6.1:
    {
        "vts": [{"vt_id": "1.3.6.1.4.1.25623.1.0.10662", "preferences": {...}}],
        "agents": [{"agent_id": "550e8400-...", "hostname": "server1.example.com"}],
        "targets": [{"hosts": "localhost", "ports": "1-65535", "credentials": {...}}],
        "scanner_preferences": {"max_checks": "4", "max_hosts": "20"}
    }

    Response: HTTP 201 Created
    {
        "scan_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "queued",
        "agents_assigned": 1
    }
    """
    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    # Validate required fields per FR-AC-001
    required_fields = ["vts", "agents", "targets"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return error_response(
            "INVALID_REQUEST",
            "Missing required fields",
            details=[{"field": field, "issue": "Required field is missing"} for field in missing_fields],
            status_code=400
        )

    # Validate agents exist and are valid UUIDs per FR-AC-001
    if not isinstance(data["agents"], list) or len(data["agents"]) == 0:
        return error_response(
            "INVALID_REQUEST",
            "At least one agent is required",
            details=[{"field": "agents", "issue": "Must be a non-empty array"}],
            status_code=400
        )

    for agent_data in data["agents"]:
        agent_id = agent_data.get("agent_id")
        if not agent_id:
            return error_response(
                "INVALID_REQUEST",
                "Each agent must have an agent_id",
                details=[{"field": "agents[].agent_id", "issue": "Required field is missing"}],
                status_code=400
            )

        # Validate UUID format per SR-VALID-001
        try:
            uuid.UUID(agent_id)
        except ValueError:
            return error_response(
                "VALIDATION_ERROR",
                "Invalid agent_id format",
                details=[{"field": "agent_id", "issue": f"Must be a valid UUID (got: {agent_id})"}],
                status_code=422
            )

    # Generate scan_id per FR-AC-001
    scan_id = str(uuid.uuid4())
    timestamp = int(datetime.utcnow().timestamp())

    # Create scan record per FR-AC-001
    scan_record = {
        "scan_id": scan_id,
        "status": "queued",
        "progress": 0,
        "agents_total": len(data["agents"]),
        "agents_running": 0,
        "agents_completed": 0,
        "agents_failed": 0,
        "start_time": timestamp,
        "end_time": None,
        "vts": data["vts"],
        "agents": data["agents"],
        "targets": data["targets"],
        "scanner_preferences": data.get("scanner_preferences", {})
    }

    scans[scan_id] = scan_record

    # Queue jobs for each agent per FR-AC-001
    job_ids = []
    for agent_data in data["agents"]:
        job_id = f"job-{uuid.uuid4()}"
        job_record = {
            "job_id": job_id,
            "scan_id": scan_id,
            "agent_id": agent_data["agent_id"],
            "job_type": "vulnerability_scan",
            "priority": "normal",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "queued",
            "config": {
                "vts": data["vts"],
                "targets": data["targets"],
                "scanner_preferences": data.get("scanner_preferences", {})
            }
        }
        scan_jobs[job_id] = job_record
        job_ids.append(job_id)

    # Initialize results storage
    scan_results[scan_id] = []

    logger.info(f"POST /scans - created scan {scan_id} with {len(job_ids)} jobs for {len(data['agents'])} agents")

    return jsonify({
        "scan_id": scan_id,
        "status": "queued",
        "agents_assigned": len(data["agents"])
    }), 201


@app.route('/scans/<scan_id>/status', methods=['GET'])
def get_scan_status(scan_id):
    """
    GET /scans/{scan_id}/status - Get scan status

    Maps to: FR-AC-002 (Scanner API - Provide Scan Status)

    Response per PRD Section 6.1:
    {
        "scan_id": "550e8400-...",
        "status": "running",
        "progress": 45,
        "agents_total": 3,
        "agents_running": 2,
        "agents_completed": 1,
        "agents_failed": 0,
        "start_time": 1705318200,
        "end_time": null
    }
    """
    if scan_id not in scans:
        return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

    scan = scans[scan_id]

    logger.info(f"GET /scans/{scan_id}/status - returning status: {scan['status']}")

    return jsonify({
        "scan_id": scan["scan_id"],
        "status": scan["status"],
        "progress": scan["progress"],
        "agents_total": scan["agents_total"],
        "agents_running": scan["agents_running"],
        "agents_completed": scan["agents_completed"],
        "agents_failed": scan["agents_failed"],
        "start_time": scan["start_time"],
        "end_time": scan["end_time"]
    }), 200


@app.route('/scans/<scan_id>/results', methods=['GET'])
def get_scan_results(scan_id):
    """
    GET /scans/{scan_id}/results - Get scan results

    Maps to: FR-AC-003 (Scanner API - Provide Scan Results)

    Supports pagination via ?range=0-99 query parameter

    Response per PRD Section 6.1:
    {
        "results": [
            {
                "result_id": "result-001",
                "agent_id": "550e8400-...",
                "agent_hostname": "server1.example.com",
                "nvt": {
                    "oid": "1.3.6.1.4.1.25623.1.0.12345",
                    "name": "OpenSSH Obsolete Version Detection",
                    "severity": 5.0,
                    "cvss_base_vector": "AV:N/AC:L/Au:N/C:N/I:N/A:N"
                },
                "host": "localhost",
                "port": "22/tcp",
                "threat": "Medium",
                "description": "The remote SSH server is running an obsolete version.",
                "qod": 80
            }
        ],
        "total_results": 245,
        "returned_results": 100
    }
    """
    if scan_id not in scans:
        return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

    # Parse range parameter per FR-AC-003
    range_param = request.args.get('range', '0-99')
    try:
        start, end = map(int, range_param.split('-'))
        if start < 0 or end < start:
            return error_response(
                "INVALID_REQUEST",
                "Invalid range parameter",
                details=[{"field": "range", "issue": "Must be in format 'start-end' where start >= 0 and end >= start"}],
                status_code=400
            )
    except ValueError:
        return error_response(
            "INVALID_REQUEST",
            "Invalid range parameter format",
            details=[{"field": "range", "issue": "Must be in format 'start-end' (e.g., '0-99')"}],
            status_code=400
        )

    # Get results for this scan
    all_results = scan_results.get(scan_id, [])
    total_results = len(all_results)

    # Apply pagination per FR-AC-003
    paginated_results = all_results[start:end+1]
    returned_results = len(paginated_results)

    logger.info(f"GET /scans/{scan_id}/results?range={range_param} - returning {returned_results}/{total_results} results")

    return jsonify({
        "results": paginated_results,
        "total_results": total_results,
        "returned_results": returned_results
    }), 200


@app.route('/scans/<scan_id>', methods=['DELETE'])
def delete_scan(scan_id):
    """
    DELETE /scans/{scan_id} - Delete a scan

    Per PRD Section 8.1 (Scanner API table)

    Response: HTTP 204 No Content
    """
    if scan_id not in scans:
        return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

    # Remove scan and associated data
    del scans[scan_id]
    if scan_id in scan_results:
        del scan_results[scan_id]

    # Remove associated jobs
    jobs_to_remove = [job_id for job_id, job in scan_jobs.items() if job.get("scan_id") == scan_id]
    for job_id in jobs_to_remove:
        del scan_jobs[job_id]

    logger.info(f"DELETE /scans/{scan_id} - deleted scan and {len(jobs_to_remove)} associated jobs")

    return '', 204


# ============================================================================
# Admin API - Endpoints for gvmd to manage agents
# Per PRD Section 6.1 (FR-AC-004 to FR-AC-006)
# ============================================================================

@app.route('/agents', methods=['GET'])
@app.route('/api/v1/admin/agents', methods=['GET'])
@require_api_key
def get_agents():
    """
    GET /agents - Return list of agents
    GET /api/v1/admin/agents - Return list of agents (actual gvmd path)
    GET /agents?updates=true - Return agents with pending updates

    Maps to:
    - agent_controller_get_agents() (agent_controller.h line 208-209)
    - agent_controller_get_agents_with_updates() (agent_controller.h line 229-230)

    Response structure matches agent_controller_agent structure (lines 125-144)
    """
    updates_only = request.args.get('updates', '').lower() == 'true'

    if updates_only:
        # Filter agents with update_to_latest == 1
        filtered_agents = [a for a in agents if a.get('update_to_latest', 0) == 1]
        logger.info(f"GET {request.path}?updates=true - returning {len(filtered_agents)} agents with updates")
        return jsonify(filtered_agents)

    logger.info(f"GET {request.path} - returning {len(agents)} agents")
    return jsonify(agents)


@app.route('/agents', methods=['PATCH'])
@app.route('/api/v1/admin/agents', methods=['PATCH'])
@require_api_key
def update_agents():
    """
    PATCH /agents - Update multiple agents (bulk operation)
    PATCH /api/v1/admin/agents - Update multiple agents (bulk operation)

    Maps to: FR-AC-005 (Admin API - Update Agents)
    Per PRD Section 6.1 and Section 8.2 (Admin API table)

    Request body:
    {
        "agents": [{"agent_id": "..."}, ...],
        "update": {
            "authorized": 1,
            "config": {...}
        }
    }

    Response:
    {
        "success": true,
        "errors": []
    }
    """
    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    if 'agents' not in data or 'update' not in data:
        missing_fields = []
        if 'agents' not in data:
            missing_fields.append({"field": "agents", "issue": "Required field is missing"})
        if 'update' not in data:
            missing_fields.append({"field": "update", "issue": "Required field is missing"})
        return error_response(
            "INVALID_REQUEST",
            "Missing required fields",
            details=missing_fields,
            status_code=400
        )

    agent_ids = [a.get('agent_id') for a in data['agents']]
    update_data = data['update']
    errors = []

    for agent_id in agent_ids:
        # Find agent in our list
        agent = next((a for a in agents if a['agent_id'] == agent_id), None)
        if not agent:
            errors.append({"agent_id": agent_id, "error": "Agent not found"})
            continue

        # Apply updates
        if 'authorized' in update_data:
            agent['authorized'] = update_data['authorized']
        if 'config' in update_data:
            agent['config'] = update_data['config']

    logger.info(f"PUT /agents - updated {len(agent_ids)} agents, {len(errors)} errors")

    if errors:
        return jsonify({"success": False, "errors": errors}), 207  # Multi-Status

    return jsonify({"success": True, "errors": []})


@app.route('/api/v1/admin/agents/delete', methods=['POST'])
@require_api_key
def delete_agents():
    """
    POST /api/v1/admin/agents/delete - Delete multiple agents

    Maps to: FR-AC-006 (Admin API - Delete Agents)
    Per PRD Section 6.1

    Request body per FR-AC-006:
    {
        "agent_ids": [
            "550e8400-e29b-41d4-a716-446655440001",
            "550e8400-e29b-41d4-a716-446655440002"
        ]
    }

    Response: HTTP 200 OK
    {
        "deleted": 2,
        "failed": 0
    }
    """
    global agents

    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    if 'agent_ids' not in data:
        return error_response(
            "INVALID_REQUEST",
            "Missing required field",
            details=[{"field": "agent_ids", "issue": "Required field is missing"}],
            status_code=400
        )

    agent_ids = data['agent_ids']
    if not isinstance(agent_ids, list):
        return error_response(
            "INVALID_REQUEST",
            "Invalid agent_ids format",
            details=[{"field": "agent_ids", "issue": "Must be an array of agent IDs"}],
            status_code=400
        )

    # Track deletion results
    deleted_count = 0
    failed_count = 0

    # Filter out agents to delete
    initial_count = len(agents)
    agents = [a for a in agents if a['agent_id'] not in agent_ids]
    deleted_count = initial_count - len(agents)
    failed_count = len(agent_ids) - deleted_count

    logger.info(f"POST /api/v1/admin/agents/delete - deleted {deleted_count} agents, {failed_count} not found")

    return jsonify({"deleted": deleted_count, "failed": failed_count}), 200


@app.route('/config', methods=['GET'])
@app.route('/api/v1/admin/config', methods=['GET'])
@require_api_key
def get_config():
    """
    GET /config - Return global scan agent configuration

    Maps to: agent_controller_get_scan_agent_config() (agent_controller.h lines 221-222)

    Response structure matches agent_controller_scan_agent_config (lines 112-117)
    """
    global global_config

    if global_config is None:
        global_config = get_default_scan_agent_config()

    logger.info("GET /config - returning scan agent configuration")
    return jsonify(global_config)


@app.route('/config', methods=['PUT', 'PATCH'])
@app.route('/api/v1/admin/config', methods=['PUT', 'PATCH'])
@require_api_key
def update_config():
    """
    PUT/PATCH /config - Update global scan agent configuration

    Maps to: agent_controller_update_scan_agent_config() (agent_controller.h lines 224-227)

    Request body: Same structure as GET /config response
    """
    global global_config

    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing configuration data in request body", status_code=400)

    global_config = data
    logger.info("PUT /config - updated scan agent configuration")

    return jsonify({"success": True, "errors": []})


@app.route('/installers', methods=['GET'])
@app.route('/api/v1/admin/installers', methods=['GET'])
@require_api_key
def get_installers():
    """
    GET /installers - Return list of available agent installers

    Phase 1: Returns empty list (will be implemented in Phase 3)

    Future structure:
    {
        "count": N,
        "installers": [
            {
                "id": "...",
                "name": "...",
                "version": "...",
                "platform": "linux|windows",
                "architecture": "amd64|arm64",
                "download_url": "...",
                "checksum": "..."
            }
        ]
    }
    """
    logger.info("GET /installers - returning empty list (Phase 1)")
    return jsonify([])


@app.route('/agents/register', methods=['POST'])
@require_api_key
def register_agent():
    """
    POST /agents/register - Manually register a new agent

    This is a helper endpoint for Phase 1 testing (not part of gvmd API)

    Request body:
    {
        "agent_id": "unique-agent-id",
        "hostname": "agent-hostname",
        "ip_addresses": ["192.168.1.100"],
        "operating_system": "Linux",
        "architecture": "amd64"
    }
    """
    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    # Check required fields
    missing_fields = []
    if 'agent_id' not in data:
        missing_fields.append({"field": "agent_id", "issue": "Required field is missing"})
    if 'hostname' not in data:
        missing_fields.append({"field": "hostname", "issue": "Required field is missing"})

    if missing_fields:
        return error_response(
            "INVALID_REQUEST",
            "Missing required fields",
            details=missing_fields,
            status_code=400
        )

    # Check if agent already exists
    if any(a['agent_id'] == data['agent_id'] for a in agents):
        return error_response(
            "CONFLICT",
            f"Agent already exists with ID: {data['agent_id']}",
            details=[{"field": "agent_id", "issue": "An agent with this ID is already registered"}],
            status_code=409
        )

    # Create new agent with structure matching agent_controller.h lines 125-144
    new_agent = {
        "agent_id": data['agent_id'],
        "hostname": data['hostname'],
        "authorized": True,  # Authorized by default (boolean)
        "connection_status": "active",
        "ip_addresses": data.get('ip_addresses', []),
        "ip_address_count": len(data.get('ip_addresses', [])),
        "last_update": int(datetime.utcnow().timestamp()),
        "last_updater_heartbeat": int(datetime.utcnow().timestamp()),
        "config": get_default_scan_agent_config(),
        "updater_version": data.get('updater_version', ""),
        "agent_version": data.get('agent_version', ""),
        "operating_system": data.get('operating_system', ""),
        "architecture": data.get('architecture', ""),
        "update_to_latest": False
    }

    agents.append(new_agent)
    logger.info(f"POST /agents/register - registered agent {data['agent_id']}")

    return jsonify({"success": True, "agent": new_agent}), 201


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with standard error format per PRD Section 8.4"""
    return error_response("NOT_FOUND", "Endpoint does not exist", status_code=404)


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with standard error format per PRD Section 8.4"""
    logger.error(f"Internal error: {error}")
    return error_response("INTERNAL_ERROR", "Internal server error", status_code=500)


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Agent Controller Service (Minimal Viable - Phase 1)")
    logger.info("=" * 60)
    logger.info(f"Starting server on {HOST}:{PORT}")
    logger.info(f"API Key: {API_KEY}")
    logger.info("")
    logger.info("Scanner API (for gvmd):")
    logger.info("  POST   /scans                - Create scan (FR-AC-001)")
    logger.info("  GET    /scans/{id}/status    - Get scan status (FR-AC-002)")
    logger.info("  GET    /scans/{id}/results   - Get scan results (FR-AC-003)")
    logger.info("  DELETE /scans/{id}           - Delete scan")
    logger.info("")
    logger.info("Admin API (requires X-API-KEY header):")
    logger.info("  GET    /api/v1/admin/agents          - List all agents (FR-AC-004)")
    logger.info("  PATCH  /api/v1/admin/agents          - Update agents (FR-AC-005)")
    logger.info("  POST   /api/v1/admin/agents/delete   - Delete agents (FR-AC-006)")
    logger.info("  GET    /api/v1/admin/config          - Get scan agent config")
    logger.info("  PUT    /api/v1/admin/config          - Update scan agent config")
    logger.info("  GET    /api/v1/admin/installers      - List installers (empty in Phase 1)")
    logger.info("")
    logger.info("Helper endpoints:")
    logger.info("  GET    /health                       - Health check (no auth)")
    logger.info("  POST   /agents/register              - Register agent (testing helper)")
    logger.info("")
    logger.info("Configure gvmd scanner:")
    logger.info("  Type: agent-controller (7)")
    logger.info(f"  Host: localhost")
    logger.info(f"  Port: {PORT}")
    logger.info("  Protocol: http")
    logger.info(f"  API Key: {API_KEY}")
    logger.info("")
    logger.info("Per PRD Section 8.4: All errors use standard format with error codes")
    logger.info("Per CLAUDE.md: NO PLACEHOLDER DATA, NO FALLBACK BEHAVIOR")
    logger.info("=" * 60)

    app.run(host=HOST, port=PORT, debug=True)
