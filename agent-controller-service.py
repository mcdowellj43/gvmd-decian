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


def require_api_key(f):
    """
    Decorator to require API key authentication (optional for now).
    Expects X-API-KEY header but allows access without it for Phase 1 testing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if api_key and api_key != API_KEY:
            logger.warning(f"Invalid API key from {request.remote_addr}")
            return jsonify({"error": "Unauthorized", "message": "Invalid API key"}), 401
        if not api_key:
            logger.debug(f"Request without API key from {request.remote_addr} (allowed in Phase 1)")
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


@app.route('/agents', methods=['PUT', 'PATCH'])
@app.route('/api/v1/admin/agents', methods=['PUT', 'PATCH'])
@require_api_key
def update_agents():
    """
    PUT/PATCH /agents - Update multiple agents (bulk operation)

    Maps to: agent_controller_update_agents() (agent_controller.h lines 211-215)

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
    if not data or 'agents' not in data or 'update' not in data:
        return jsonify({"error": "Invalid request", "message": "Missing 'agents' or 'update' fields"}), 400

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


@app.route('/agents', methods=['DELETE'])
@app.route('/api/v1/admin/agents', methods=['DELETE'])
@require_api_key
def delete_agents():
    """
    DELETE /agents - Delete multiple agents

    Maps to: agent_controller_delete_agents() (agent_controller.h lines 217-219)

    Request body:
    {
        "agents": [{"agent_id": "..."}, ...]
    }
    """
    global agents

    data = request.get_json()
    if not data or 'agents' not in data:
        return jsonify({"error": "Invalid request", "message": "Missing 'agents' field"}), 400

    agent_ids = [a.get('agent_id') for a in data['agents']]

    # Filter out agents to delete
    agents = [a for a in agents if a['agent_id'] not in agent_ids]

    logger.info(f"DELETE /agents - deleted {len(agent_ids)} agents")
    return jsonify({"success": True})


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
        return jsonify({"error": "Invalid request", "message": "Missing configuration data"}), 400

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
    if not data or 'agent_id' not in data or 'hostname' not in data:
        return jsonify({"error": "Invalid request", "message": "Missing required fields"}), 400

    # Check if agent already exists
    if any(a['agent_id'] == data['agent_id'] for a in agents):
        return jsonify({"error": "Agent already exists"}), 409

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
    return jsonify({"error": "Not found", "message": "Endpoint does not exist"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Agent Controller Service (Minimal Viable - Phase 1)")
    logger.info("=" * 60)
    logger.info(f"Starting server on {HOST}:{PORT}")
    logger.info(f"API Key: {API_KEY}")
    logger.info("")
    logger.info("Endpoints:")
    logger.info("  GET  /health              - Health check (no auth)")
    logger.info("  GET  /agents              - List all agents")
    logger.info("  GET  /agents?updates=true - List agents with updates")
    logger.info("  PUT  /agents              - Update agents")
    logger.info("  DELETE /agents            - Delete agents")
    logger.info("  GET  /config              - Get scan agent config")
    logger.info("  PUT  /config              - Update scan agent config")
    logger.info("  GET  /installers          - List installers (empty in Phase 1)")
    logger.info("  POST /agents/register     - Register agent (testing helper)")
    logger.info("")
    logger.info("Configure gvmd scanner:")
    logger.info("  Type: agent-controller (7)")
    logger.info(f"  Host: localhost")
    logger.info(f"  Port: {PORT}")
    logger.info("  Protocol: http")
    logger.info(f"  API Key: {API_KEY}")
    logger.info("=" * 60)

    app.run(host=HOST, port=PORT, debug=True)
