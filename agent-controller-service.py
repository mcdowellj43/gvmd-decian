#!/usr/bin/env python3
"""
Minimal Viable Agent Controller Service
Compatible with Greenbone gvmd agent-controller scanner type.

This service implements the REST API expected by gvm-libs agent_controller client. Test
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
import os
import sqlite3
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_KEY = os.environ.get("API_KEY", "test-api-key-12345")  # Change this in production
PORT = int(os.environ.get("PORT", 3001))
HOST = os.environ.get("HOST", "0.0.0.0")

# Database configuration
DB_PATH = '/app/agent_controller.db'

global_config = None


def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create agents table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            hostname TEXT NOT NULL,
            authorized INTEGER DEFAULT 0,
            connection_status TEXT DEFAULT 'inactive',
            last_update INTEGER,
            last_updater_heartbeat INTEGER,
            config TEXT,
            updater_version TEXT DEFAULT '',
            agent_version TEXT DEFAULT '',
            operating_system TEXT DEFAULT '',
            architecture TEXT DEFAULT '',
            update_to_latest INTEGER DEFAULT 0
        )
    """)

    # Create agent_ip_addresses table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_ip_addresses (
            agent_id TEXT,
            ip_address TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
        )
    """)

    conn.commit()
    conn.close()


def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_agents_from_db(updates_only=False):
    """Fetch agents from the database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if updates_only:
            cur.execute("SELECT * FROM agents WHERE update_to_latest = 1")
        else:
            cur.execute("SELECT * FROM agents")

        rows = cur.fetchall()

        # Convert to the format expected by the API
        agents = []
        for row in rows:
            # Get IP addresses for this agent
            cur.execute("SELECT ip_address FROM agent_ip_addresses WHERE agent_id = ?", (row['agent_id'],))
            ip_rows = cur.fetchall()
            ip_addresses = [ip_row['ip_address'] for ip_row in ip_rows]

            agent = {
                "agentid": row['agent_id'],
                "hostname": row['hostname'],
                "authorized": bool(row['authorized']),  # Convert integer to boolean
                "connection_status": row['connection_status'],
                "ip_addresses": ip_addresses,
                "ip_address_count": len(ip_addresses),
                "last_update": row['last_update'],
                "last_updater_heartbeat": row['last_updater_heartbeat'],
                "config": json.loads(row['config']) if row['config'] else get_default_scan_agent_config(),
                "updater_version": row['updater_version'] or '',
                "agent_version": row['agent_version'] or '',
                "operating_system": row['operating_system'] or '',
                "architecture": row['architecture'] or '',
                "update_to_latest": bool(row['update_to_latest'])
            }
            agents.append(agent)

        cur.close()
        conn.close()
        return agents

    except Exception as e:
        logger.error(f"Database error in get_agents_from_db: {e}")
        return []


def update_agent_in_db(agent_id, updates):
    """Update an agent in the database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Build the SET clause dynamically
        set_clauses = []
        params = []

        if 'authorized' in updates:
            set_clauses.append("authorized = ?")
            params.append(updates['authorized'])

        if 'config' in updates:
            set_clauses.append("config = ?")
            params.append(json.dumps(updates['config']))

        if set_clauses:
            params.append(agent_id)
            query = f"UPDATE agents SET {', '.join(set_clauses)} WHERE agent_id = ?"
            logger.info(f"Executing UPDATE query: {query} with params: {params}")
            cur.execute(query, params)
            conn.commit()

            affected_rows = cur.rowcount
            logger.info(f"UPDATE affected {affected_rows} rows for agent_id: {agent_id}")
            cur.close()
            conn.close()
            return affected_rows > 0

        cur.close()
        conn.close()
        return False

    except Exception as e:
        logger.error(f"Database error in update_agent_in_db: {e}")
        return False


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

    agents = get_agents_from_db(updates_only)

    logger.info(f"GET {request.path} - returning {len(agents)} agents from database")
    logger.info(f"DEBUG GET: Headers from GVMD: {dict(request.headers)}")
    response = jsonify(agents)
    logger.info(f"DEBUG GET: Status to GVMD: {response.status}")
    return response

    


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
    logger.info(f"PATCH /agents - received data: {data}")
    logger.info(f"DEBUG PATCH: Headers from GVMD: {dict(request.headers)}")
    # Handle the actual format GVMD sends: {"agent-001": {"authorized": True}, ...}
    if isinstance(data, dict):
        logger.info(f"PATCH /agents - handling GVMD format with {len(data)} agents")
        errors = []
        for agent_id, update_data in data.items():
            # Prepare updates for database
            db_updates = {}

            # Apply updates (convert True/False to 1/0 for authorized)
            if "authorized" in update_data:
                db_updates["authorized"] = 1 if update_data["authorized"] else 0
            if "config" in update_data:
                db_updates["config"] = update_data["config"]

            # Update in database
            if db_updates:
                success = update_agent_in_db(agent_id, db_updates)
                if not success:
                    errors.append({"agent_id": agent_id, "error": "Agent not found or update failed"})

        logger.info(f"PATCH /agents - updated {len(data) - len(errors)} agents, {len(errors)} errors")
        if errors:
            logger.info(f"DEBUG PATCH: Returning 207 with errors: {errors}")

            return jsonify({"success": False, "errors": errors}), 207
        logger.info(f"DEBUG PATCH: Returning 200 success")
        return jsonify({"success": True, "errors": []})
    else:
        logger.error(f"PATCH /agents - Unexpected data format: {type(data)}")
        return jsonify({"error": "Invalid request format"}), 400


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
    data = request.get_json()
    if not data or 'agents' not in data:
        return jsonify({"error": "Invalid request", "message": "Missing 'agents' field"}), 400

    agent_ids = [a.get('agent_id') for a in data['agents']]

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for agent_id in agent_ids:
            # Delete IP addresses first
            cur.execute("DELETE FROM agent_ip_addresses WHERE agent_id = ?", (agent_id,))
            # Delete agent
            cur.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"DELETE /agents - deleted {len(agent_ids)} agents from database")
    except Exception as e:
        logger.error(f"Database error in delete_agents: {e}")
        return jsonify({"error": "Database error"}), 500

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

    # Check if agent already exists in database
    existing_agents = get_agents_from_db()
    if any(a['agentid'] == data['agent_id'] for a in existing_agents):
        return jsonify({"error": "Agent already exists"}), 409

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Insert agent into database
        cur.execute("""
            INSERT INTO agents (
                agent_id, hostname, authorized, connection_status, last_update,
                last_updater_heartbeat, config, updater_version, agent_version,
                operating_system, architecture, update_to_latest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['agent_id'],
            data['hostname'],
            0,  # Not authorized by default
            'active',
            int(datetime.utcnow().timestamp()),
            int(datetime.utcnow().timestamp()),
            json.dumps(get_default_scan_agent_config()),
            data.get('updater_version', ''),
            data.get('agent_version', ''),
            data.get('operating_system', ''),
            data.get('architecture', ''),
            0
        ))

        # Insert IP addresses
        for ip_address in data.get('ip_addresses', []):
            cur.execute(
                "INSERT INTO agent_ip_addresses (agent_id, ip_address) VALUES (?, ?)",
                (data['agent_id'], ip_address)
            )

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"POST /agents/register - registered agent {data['agent_id']} in database")

        # Return the created agent structure
        new_agent = {
            "agentid": data['agent_id'],
            "hostname": data['hostname'],
            "authorized": False,
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

        return jsonify({"success": True, "agent": new_agent}), 201

    except Exception as e:
        logger.error(f"Database error in register_agent: {e}")
        return jsonify({"error": "Database error"}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found", "message": "Endpoint does not exist"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    # Initialize database on startup
    init_database()

    logger.info("=" * 60)
    logger.info("Agent Controller Service (Minimal Viable - Phase 1 - SQLite)")
    logger.info("=" * 60)
    logger.info(f"Starting server on {HOST}:{PORT}")
    logger.info(f"API Key: {API_KEY}")
    logger.info(f"Database: {DB_PATH}")
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
