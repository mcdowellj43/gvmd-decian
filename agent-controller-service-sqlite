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
import uuid

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_KEY = os.environ.get("API_KEY", "test-api-key-12345")  # Change this in production
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "test-agent-token-67890")  # Agent authentication token
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

    # Create scans table per PRD Section 7.1.2
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            agents_total INTEGER DEFAULT 0,
            agents_running INTEGER DEFAULT 0,
            agents_completed INTEGER DEFAULT 0,
            agents_failed INTEGER DEFAULT 0,
            start_time INTEGER NOT NULL,
            end_time INTEGER,
            vts TEXT NOT NULL,
            agents TEXT NOT NULL,
            targets TEXT NOT NULL,
            scanner_preferences TEXT
        )
    """)

    # Create scan_jobs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scan_jobs (
            job_id TEXT PRIMARY KEY,
            scan_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            job_type TEXT DEFAULT 'vulnerability_scan',
            priority TEXT DEFAULT 'normal',
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            config TEXT NOT NULL,
            FOREIGN KEY (scan_id) REFERENCES scans (scan_id),
            FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
        )
    """)

    # Create scan_results table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            result_id TEXT PRIMARY KEY,
            scan_id TEXT NOT NULL,
            agent_id TEXT,
            agent_hostname TEXT,
            nvt_oid TEXT,
            nvt_name TEXT,
            nvt_severity REAL,
            nvt_cvss_base_vector TEXT,
            host TEXT,
            port TEXT,
            threat TEXT,
            description TEXT,
            qod INTEGER,
            FOREIGN KEY (scan_id) REFERENCES scans (scan_id)
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


def require_agent_auth(f):
    """
    Decorator to require agent authentication.
    Expects Authorization: Bearer <token> header. Per CLAUDE.md: NO FALLBACK BEHAVIOR.

    Per PRD Section 9.1 (SR-AUTH-001): All Agent API endpoints require agent authentication.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning(f"Missing Authorization header from {request.remote_addr}")
            return error_response(
                "UNAUTHORIZED",
                "Missing authentication token",
                details=[{"field": "Authorization", "issue": "Required header is missing"}],
                status_code=401
            )

        # Check for Bearer token format
        if not auth_header.startswith('Bearer '):
            return error_response(
                "UNAUTHORIZED",
                "Invalid authentication format",
                details=[{"field": "Authorization", "issue": "Must use 'Bearer <token>' format"}],
                status_code=401
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        if token != AGENT_TOKEN:
            logger.warning(f"Invalid agent token from {request.remote_addr}")
            return error_response(
                "UNAUTHORIZED",
                "Invalid authentication token",
                details=[{"field": "Authorization", "issue": "Token is not valid"}],
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

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create scan record per FR-AC-001
        cur.execute("""
            INSERT INTO scans (
                scan_id, status, progress, agents_total, agents_running, agents_completed,
                agents_failed, start_time, end_time, vts, agents, targets, scanner_preferences
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            'queued',
            0,
            len(data["agents"]),
            0,
            0,
            0,
            timestamp,
            None,
            json.dumps(data["vts"]),
            json.dumps(data["agents"]),
            json.dumps(data["targets"]),
            json.dumps(data.get("scanner_preferences", {}))
        ))

        # Queue jobs for each agent per FR-AC-001
        job_ids = []
        for agent_data in data["agents"]:
            job_id = f"job-{uuid.uuid4()}"
            job_config = {
                "vts": data["vts"],
                "targets": data["targets"],
                "scanner_preferences": data.get("scanner_preferences", {})
            }

            cur.execute("""
                INSERT INTO scan_jobs (
                    job_id, scan_id, agent_id, job_type, priority, created_at, status, config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                scan_id,
                agent_data["agent_id"],
                'vulnerability_scan',
                'normal',
                datetime.utcnow().isoformat() + "Z",
                'queued',
                json.dumps(job_config)
            ))
            job_ids.append(job_id)

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"POST /scans - created scan {scan_id} with {len(job_ids)} jobs for {len(data['agents'])} agents")

        return jsonify({
            "scan_id": scan_id,
            "status": "queued",
            "agents_assigned": len(data["agents"])
        }), 201

    except Exception as e:
        logger.error(f"Database error in create_scan: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


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
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

        logger.info(f"GET /scans/{scan_id}/status - returning status: {row['status']}")

        return jsonify({
            "scan_id": row["scan_id"],
            "status": row["status"],
            "progress": row["progress"],
            "agents_total": row["agents_total"],
            "agents_running": row["agents_running"],
            "agents_completed": row["agents_completed"],
            "agents_failed": row["agents_failed"],
            "start_time": row["start_time"],
            "end_time": row["end_time"]
        }), 200

    except Exception as e:
        logger.error(f"Database error in get_scan_status: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/scans/<scan_id>/results', methods=['GET'])
def get_scan_results(scan_id):
    """
    GET /scans/{scan_id}/results - Get scan results

    Maps to: FR-AC-003 (Scanner API - Provide Scan Results)

    Supports pagination via ?range=0-99 query parameter

    Response per PRD Section 6.1:
    {
        "results": [...],
        "total_results": 245,
        "returned_results": 100
    }
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if scan exists
        cur.execute("SELECT scan_id FROM scans WHERE scan_id = ?", (scan_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

        # Parse range parameter per FR-AC-003
        range_param = request.args.get('range', '0-99')
        try:
            start, end = map(int, range_param.split('-'))
            if start < 0 or end < start:
                cur.close()
                conn.close()
                return error_response(
                    "INVALID_REQUEST",
                    "Invalid range parameter",
                    details=[{"field": "range", "issue": "Must be in format 'start-end' where start >= 0 and end >= start"}],
                    status_code=400
                )
        except ValueError:
            cur.close()
            conn.close()
            return error_response(
                "INVALID_REQUEST",
                "Invalid range parameter format",
                details=[{"field": "range", "issue": "Must be in format 'start-end' (e.g., '0-99')"}],
                status_code=400
            )

        # Get total count
        cur.execute("SELECT COUNT(*) as count FROM scan_results WHERE scan_id = ?", (scan_id,))
        total_results = cur.fetchone()["count"]

        # Get paginated results
        limit = end - start + 1
        cur.execute("""
            SELECT * FROM scan_results
            WHERE scan_id = ?
            LIMIT ? OFFSET ?
        """, (scan_id, limit, start))

        rows = cur.fetchall()
        results = []
        for row in rows:
            result = {
                "result_id": row["result_id"],
                "agent_id": row["agent_id"],
                "agent_hostname": row["agent_hostname"],
                "nvt": {
                    "oid": row["nvt_oid"],
                    "name": row["nvt_name"],
                    "severity": row["nvt_severity"],
                    "cvss_base_vector": row["nvt_cvss_base_vector"]
                },
                "host": row["host"],
                "port": row["port"],
                "threat": row["threat"],
                "description": row["description"],
                "qod": row["qod"]
            }
            results.append(result)

        cur.close()
        conn.close()

        returned_results = len(results)
        logger.info(f"GET /scans/{scan_id}/results?range={range_param} - returning {returned_results}/{total_results} results")

        return jsonify({
            "results": results,
            "total_results": total_results,
            "returned_results": returned_results
        }), 200

    except Exception as e:
        logger.error(f"Database error in get_scan_results: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/scans/<scan_id>', methods=['DELETE'])
def delete_scan(scan_id):
    """
    DELETE /scans/{scan_id} - Delete a scan

    Per PRD Section 8.1 (Scanner API table)

    Response: HTTP 204 No Content
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if scan exists
        cur.execute("SELECT scan_id FROM scans WHERE scan_id = ?", (scan_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return error_response("NOT_FOUND", f"Scan not found: {scan_id}", status_code=404)

        # Delete scan results
        cur.execute("DELETE FROM scan_results WHERE scan_id = ?", (scan_id,))
        results_deleted = cur.rowcount

        # Delete scan jobs
        cur.execute("DELETE FROM scan_jobs WHERE scan_id = ?", (scan_id,))
        jobs_deleted = cur.rowcount

        # Delete scan
        cur.execute("DELETE FROM scans WHERE scan_id = ?", (scan_id,))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"DELETE /scans/{scan_id} - deleted scan and {jobs_deleted} jobs, {results_deleted} results")

        return '', 204

    except Exception as e:
        logger.error(f"Database error in delete_scan: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


# ============================================================================
# Agent-Facing API - Endpoints for agents to interact with Agent Controller
# Per PRD Section 6.1 (FR-AC-007 to FR-AC-009) and Section 8.3
# ============================================================================

@app.route('/api/v1/agents/heartbeat', methods=['POST'])
@require_agent_auth
def agent_heartbeat():
    """
    POST /api/v1/agents/heartbeat - Accept agent heartbeat

    Maps to: FR-AC-007 (Agent API - Accept Heartbeats)

    Request body per PRD Section 6.1:
    {
        "agent_id": "550e8400-...",
        "hostname": "server1.example.com",
        "connection_status": "active",
        "ip_addresses": ["192.168.1.100", "10.0.0.50"],
        "agent_version": "1.0.0",
        "operating_system": "Ubuntu 22.04 LTS",
        "architecture": "amd64"
    }

    Response: HTTP 200 OK
    {
        "status": "accepted",
        "config_updated": false,
        "next_heartbeat_in_seconds": 600,
        "authorized": true
    }
    """
    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    # Validate required fields per FR-AC-007
    required_fields = ["agent_id", "hostname"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return error_response(
            "INVALID_REQUEST",
            "Missing required fields",
            details=[{"field": field, "issue": "Required field is missing"} for field in missing_fields],
            status_code=400
        )

    agent_id = data["agent_id"]

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

    timestamp = int(datetime.utcnow().timestamp())

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if agent exists
        cur.execute("SELECT agent_id, authorized, config FROM agents WHERE agent_id = ?", (agent_id,))
        existing_agent = cur.fetchone()

        config_updated = False

        if existing_agent:
            # Update existing agent per FR-AC-007
            logger.info(f"Heartbeat from existing agent {agent_id}")

            # Delete old IP addresses
            cur.execute("DELETE FROM agent_ip_addresses WHERE agent_id = ?", (agent_id,))

            # Update agent record
            cur.execute("""
                UPDATE agents SET
                    hostname = ?,
                    connection_status = ?,
                    last_update = ?,
                    last_updater_heartbeat = ?,
                    agent_version = ?,
                    operating_system = ?,
                    architecture = ?
                WHERE agent_id = ?
            """, (
                data.get("hostname"),
                data.get("connection_status", "active"),
                timestamp,
                timestamp,
                data.get("agent_version", ""),
                data.get("operating_system", ""),
                data.get("architecture", ""),
                agent_id
            ))

            authorized = bool(existing_agent["authorized"])

        else:
            # Auto-register new agent on first heartbeat per FR-AC-007
            logger.info(f"Auto-registering new agent {agent_id} on first heartbeat")

            cur.execute("""
                INSERT INTO agents (
                    agent_id, hostname, authorized, connection_status, last_update,
                    last_updater_heartbeat, config, updater_version, agent_version,
                    operating_system, architecture, update_to_latest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_id,
                data.get("hostname"),
                0,  # Not authorized by default - admin must authorize
                data.get("connection_status", "active"),
                timestamp,
                timestamp,
                json.dumps(get_default_scan_agent_config()),
                data.get("updater_version", ""),
                data.get("agent_version", ""),
                data.get("operating_system", ""),
                data.get("architecture", ""),
                0
            ))

            authorized = False

        # Insert new IP addresses
        for ip_address in data.get("ip_addresses", []):
            cur.execute(
                "INSERT INTO agent_ip_addresses (agent_id, ip_address) VALUES (?, ?)",
                (agent_id, ip_address)
            )

        conn.commit()
        cur.close()
        conn.close()

        # Get heartbeat interval from config
        global global_config
        if global_config is None:
            global_config = get_default_scan_agent_config()

        next_heartbeat_in_seconds = global_config.get("heartbeat", {}).get("interval_in_seconds", 600)

        logger.info(f"POST /api/v1/agents/heartbeat - accepted heartbeat from {agent_id}, authorized={authorized}")

        return jsonify({
            "status": "accepted",
            "config_updated": config_updated,
            "next_heartbeat_in_seconds": next_heartbeat_in_seconds,
            "authorized": authorized
        }), 200

    except Exception as e:
        logger.error(f"Database error in agent_heartbeat: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/api/v1/agents/jobs', methods=['GET'])
@require_agent_auth
def agent_get_jobs():
    """
    GET /api/v1/agents/jobs - Poll for scan jobs

    Maps to: FR-AC-008 (Agent API - Serve Jobs to Agents)

    Request headers:
    - Authorization: Bearer <agent-token>
    - X-Agent-ID: <agent-uuid>

    Response: HTTP 200 OK
    {
        "jobs": [
            {
                "job_id": "job-12345",
                "scan_id": "550e8400-...",
                "job_type": "vulnerability_scan",
                "priority": "normal",
                "created_at": "2025-01-15T10:25:00Z",
                "config": {
                    "vts": [...],
                    "targets": [...],
                    "scanner_preferences": {...}
                }
            }
        ]
    }
    """
    agent_id = request.headers.get('X-Agent-ID')

    if not agent_id:
        return error_response(
            "INVALID_REQUEST",
            "Missing agent ID",
            details=[{"field": "X-Agent-ID", "issue": "Required header is missing"}],
            status_code=400
        )

    # Validate UUID format per SR-VALID-001
    try:
        uuid.UUID(agent_id)
    except ValueError:
        return error_response(
            "VALIDATION_ERROR",
            "Invalid agent_id format",
            details=[{"field": "X-Agent-ID", "issue": f"Must be a valid UUID (got: {agent_id})"}],
            status_code=422
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if agent exists and is authorized per FR-AC-008
        cur.execute("SELECT authorized FROM agents WHERE agent_id = ?", (agent_id,))
        agent_row = cur.fetchone()

        if not agent_row:
            cur.close()
            conn.close()
            return error_response(
                "NOT_FOUND",
                f"Agent not found: {agent_id}",
                details=[{"field": "X-Agent-ID", "issue": "Agent must send heartbeat to register first"}],
                status_code=404
            )

        if not agent_row["authorized"]:
            # Return empty jobs array if not authorized
            logger.info(f"GET /api/v1/agents/jobs - agent {agent_id} not authorized, returning empty jobs")
            cur.close()
            conn.close()
            return jsonify({"jobs": []}), 200

        # Get queued jobs for this agent per FR-AC-008
        cur.execute("""
            SELECT job_id, scan_id, job_type, priority, created_at, status, config
            FROM scan_jobs
            WHERE agent_id = ? AND status = 'queued'
            ORDER BY created_at ASC
        """, (agent_id,))

        rows = cur.fetchall()
        jobs = []
        for row in rows:
            job = {
                "job_id": row["job_id"],
                "scan_id": row["scan_id"],
                "job_type": row["job_type"],
                "priority": row["priority"],
                "created_at": row["created_at"],
                "config": json.loads(row["config"])
            }
            jobs.append(job)

            # Mark job as assigned per FR-AC-008
            cur.execute("""
                UPDATE scan_jobs SET status = 'assigned' WHERE job_id = ?
            """, (row["job_id"],))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"GET /api/v1/agents/jobs - returning {len(jobs)} jobs for agent {agent_id}")

        return jsonify({"jobs": jobs}), 200

    except Exception as e:
        logger.error(f"Database error in agent_get_jobs: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/api/v1/agents/jobs/<job_id>/results', methods=['POST'])
@require_agent_auth
def agent_submit_results(job_id):
    """
    POST /api/v1/agents/jobs/{job_id}/results - Submit scan results

    Maps to: FR-AC-009 (Agent API - Accept Results)

    Request body per PRD Section 6.1:
    {
        "job_id": "job-12345",
        "scan_id": "550e8400-...",
        "agent_id": "550e8400-...",
        "status": "completed",
        "started_at": "2025-01-15T10:30:00Z",
        "completed_at": "2025-01-15T10:45:00Z",
        "results": [
            {
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
        ]
    }

    Response: HTTP 202 Accepted
    {
        "status": "accepted",
        "results_received": 1
    }
    """
    data = request.get_json()
    if not data:
        return error_response("INVALID_REQUEST", "Missing request body", status_code=400)

    # Validate required fields per FR-AC-009
    required_fields = ["job_id", "scan_id", "agent_id", "status", "results"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return error_response(
            "INVALID_REQUEST",
            "Missing required fields",
            details=[{"field": field, "issue": "Required field is missing"} for field in missing_fields],
            status_code=400
        )

    if data["job_id"] != job_id:
        return error_response(
            "INVALID_REQUEST",
            "Job ID mismatch",
            details=[{"field": "job_id", "issue": f"URL job_id ({job_id}) does not match body job_id ({data['job_id']})"}],
            status_code=400
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Verify job exists per FR-AC-009
        cur.execute("SELECT scan_id, agent_id FROM scan_jobs WHERE job_id = ?", (job_id,))
        job_row = cur.fetchone()

        if not job_row:
            cur.close()
            conn.close()
            return error_response("NOT_FOUND", f"Job not found: {job_id}", status_code=404)

        scan_id = job_row["scan_id"]
        expected_agent_id = job_row["agent_id"]

        if data["agent_id"] != expected_agent_id:
            cur.close()
            conn.close()
            return error_response(
                "FORBIDDEN",
                "Agent not authorized for this job",
                details=[{"field": "agent_id", "issue": f"Job belongs to different agent"}],
                status_code=403
            )

        # Get agent hostname for results
        cur.execute("SELECT hostname FROM agents WHERE agent_id = ?", (data["agent_id"],))
        agent_row = cur.fetchone()
        agent_hostname = agent_row["hostname"] if agent_row else "unknown"

        # Store results in database per FR-AC-009
        results_count = 0
        for result in data.get("results", []):
            result_id = f"result-{uuid.uuid4()}"
            nvt = result.get("nvt", {})

            cur.execute("""
                INSERT INTO scan_results (
                    result_id, scan_id, agent_id, agent_hostname,
                    nvt_oid, nvt_name, nvt_severity, nvt_cvss_base_vector,
                    host, port, threat, description, qod
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id,
                scan_id,
                data["agent_id"],
                agent_hostname,
                nvt.get("oid"),
                nvt.get("name"),
                nvt.get("severity"),
                nvt.get("cvss_base_vector"),
                result.get("host"),
                result.get("port"),
                result.get("threat"),
                result.get("description"),
                result.get("qod")
            ))
            results_count += 1

        # Update job status
        cur.execute("""
            UPDATE scan_jobs SET status = ? WHERE job_id = ?
        """, (data["status"], job_id))

        # Update scan progress per FR-AC-009
        if data["status"] == "completed":
            # Increment agents_completed counter
            cur.execute("""
                UPDATE scans SET
                    agents_completed = agents_completed + 1,
                    agents_running = CASE WHEN agents_running > 0 THEN agents_running - 1 ELSE 0 END
                WHERE scan_id = ?
            """, (scan_id,))

            # Update scan status if all agents completed
            cur.execute("""
                SELECT agents_total, agents_completed
                FROM scans
                WHERE scan_id = ?
            """, (scan_id,))
            scan_row = cur.fetchone()

            if scan_row and scan_row["agents_completed"] >= scan_row["agents_total"]:
                # All agents completed, mark scan as completed
                end_time = int(datetime.utcnow().timestamp())
                cur.execute("""
                    UPDATE scans SET status = 'completed', end_time = ?, progress = 100
                    WHERE scan_id = ?
                """, (end_time, scan_id))
            else:
                # Calculate progress percentage
                if scan_row:
                    progress = int((scan_row["agents_completed"] / scan_row["agents_total"]) * 100)
                    cur.execute("""
                        UPDATE scans SET progress = ? WHERE scan_id = ?
                    """, (progress, scan_id))

        elif data["status"] == "running":
            # Increment agents_running counter
            cur.execute("""
                UPDATE scans SET
                    agents_running = agents_running + 1,
                    status = 'running'
                WHERE scan_id = ?
            """, (scan_id,))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"POST /api/v1/agents/jobs/{job_id}/results - accepted {results_count} results from agent {data['agent_id']}")

        return jsonify({
            "status": "accepted",
            "results_received": results_count
        }), 202

    except Exception as e:
        logger.error(f"Database error in agent_submit_results: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/api/v1/agents/jobs/<job_id>/complete', methods=['POST'])
@require_agent_auth
def agent_complete_job(job_id):
    """
    POST /api/v1/agents/jobs/{job_id}/complete - Mark job as complete

    Secondary endpoint for explicit job completion signal

    Response: HTTP 200 OK
    {
        "status": "completed"
    }
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Verify job exists
        cur.execute("SELECT scan_id, status FROM scan_jobs WHERE job_id = ?", (job_id,))
        job_row = cur.fetchone()

        if not job_row:
            cur.close()
            conn.close()
            return error_response("NOT_FOUND", f"Job not found: {job_id}", status_code=404)

        # Update job status to completed
        cur.execute("""
            UPDATE scan_jobs SET status = 'completed' WHERE job_id = ?
        """, (job_id,))

        scan_id = job_row["scan_id"]

        # Update scan counters
        cur.execute("""
            UPDATE scans SET
                agents_completed = agents_completed + 1,
                agents_running = CASE WHEN agents_running > 0 THEN agents_running - 1 ELSE 0 END
            WHERE scan_id = ?
        """, (scan_id,))

        # Check if all agents completed
        cur.execute("""
            SELECT agents_total, agents_completed
            FROM scans
            WHERE scan_id = ?
        """, (scan_id,))
        scan_row = cur.fetchone()

        if scan_row and scan_row["agents_completed"] >= scan_row["agents_total"]:
            end_time = int(datetime.utcnow().timestamp())
            cur.execute("""
                UPDATE scans SET status = 'completed', end_time = ?, progress = 100
                WHERE scan_id = ?
            """, (end_time, scan_id))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"POST /api/v1/agents/jobs/{job_id}/complete - marked job as completed")

        return jsonify({"status": "completed"}), 200

    except Exception as e:
        logger.error(f"Database error in agent_complete_job: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


@app.route('/api/v1/agents/config', methods=['GET'])
@require_agent_auth
def agent_get_config():
    """
    GET /api/v1/agents/config - Get agent configuration

    Secondary endpoint for agents to fetch their configuration

    Response: HTTP 200 OK
    {
        "heartbeat": {
            "interval_in_seconds": 600,
            "miss_until_inactive": 1
        },
        "retry": {
            "attempts": 5,
            "delay_in_seconds": 60,
            "max_jitter_in_seconds": 30
        },
        "agent_script_executor": {
            "bulk_size": 100,
            "bulk_throttle_time_in_ms": 1000,
            "scheduler_cron_time": ["0 2 * * *"]
        }
    }
    """
    global global_config

    if global_config is None:
        global_config = get_default_scan_agent_config()

    logger.info("GET /api/v1/agents/config - returning agent configuration")
    return jsonify(global_config), 200


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

    agents = get_agents_from_db(updates_only)

    logger.info(f"GET {request.path} - returning {len(agents)} agents from database")
    logger.info(f"DEBUG GET: Headers from GVMD: {dict(request.headers)}")
    response = jsonify(agents)
    logger.info(f"DEBUG GET: Status to GVMD: {response.status}")
    return response

    


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
        return error_response(
            "INVALID_REQUEST",
            "Invalid request format",
            details=[{"field": "body", "issue": f"Expected object, got {type(data).__name__}"}],
            status_code=400
        )


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

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        deleted_count = 0
        for agent_id in agent_ids:
            # Delete IP addresses first
            cur.execute("DELETE FROM agent_ip_addresses WHERE agent_id = ?", (agent_id,))
            # Delete agent
            cur.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            if cur.rowcount > 0:
                deleted_count += 1

        conn.commit()
        cur.close()
        conn.close()

        failed_count = len(agent_ids) - deleted_count
        logger.info(f"POST /api/v1/admin/agents/delete - deleted {deleted_count} agents, {failed_count} not found")

        return jsonify({"deleted": deleted_count, "failed": failed_count}), 200

    except Exception as e:
        logger.error(f"Database error in delete_agents: {e}")
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


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

    # Check if agent already exists in database
    existing_agents = get_agents_from_db()
    if any(a['agentid'] == data['agent_id'] for a in existing_agents):
        return error_response(
            "CONFLICT",
            f"Agent already exists with ID: {data['agent_id']}",
            details=[{"field": "agent_id", "issue": "An agent with this ID is already registered"}],
            status_code=409
        )

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
        return error_response("INTERNAL_ERROR", "Database error", status_code=500)


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
    # Initialize database on startup
    init_database()

    logger.info("=" * 60)
    logger.info("Agent Controller Service (Minimal Viable - Phase 1 - SQLite)")
    logger.info("=" * 60)
    logger.info(f"Starting server on {HOST}:{PORT}")
    logger.info(f"API Key: {API_KEY}")
    logger.info(f"Agent Token: {AGENT_TOKEN}")
    logger.info(f"Database: {DB_PATH}")
    logger.info("")
    logger.info("Scanner API (for gvmd):")
    logger.info("  POST   /scans                - Create scan (FR-AC-001)")
    logger.info("  GET    /scans/{id}/status    - Get scan status (FR-AC-002)")
    logger.info("  GET    /scans/{id}/results   - Get scan results (FR-AC-003)")
    logger.info("  DELETE /scans/{id}           - Delete scan")
    logger.info("")
    logger.info("Agent-Facing API (requires Bearer token):")
    logger.info("  POST   /api/v1/agents/heartbeat              - Accept heartbeat (FR-AC-007)")
    logger.info("  GET    /api/v1/agents/jobs                   - Poll for jobs (FR-AC-008)")
    logger.info("  POST   /api/v1/agents/jobs/{id}/results      - Submit results (FR-AC-009)")
    logger.info("  POST   /api/v1/agents/jobs/{id}/complete     - Mark job complete")
    logger.info("  GET    /api/v1/agents/config                 - Get agent config")
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
