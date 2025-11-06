# Enabling Agent and Container Scanning Features in GVM

## Problem Summary

After installing the gvmd backend (Greenbone Vulnerability Manager), the GSA web interface at `http://localhost:9392` was not displaying agent management, customer management, or container scanning features.

## Root Cause

The issue had **two separate problems** that needed to be resolved:

### 1. Backend Issue: Features Not Compiled
The Debian/Kali package for `gvmd` (version 26.2.1) was **compiled without agent support**. The binary was built with:
- `ENABLE_AGENTS=0` (disabled)
- `ENABLE_CONTAINER_SCANNING=0` (disabled)

These are **compile-time flags** that cannot be changed without rebuilding the binary from source.

### 2. Frontend Issue: Version Mismatch
Even after enabling backend features, the GSA frontend (version 24.5.4) was **too old** to display the agent management UI components. The frontend and backend versions need to match for all features to be visible.

## Solution Overview

To enable agent and customer features, we needed to:
1. Upgrade `gvm-libs` to version 22.30.0
2. Rebuild `gvmd` v26.6.0 with `ENABLE_AGENTS=1` and `ENABLE_CONTAINER_SCANNING=1`
3. Build and deploy GSA frontend v26.2.0 to match the backend

---

## Step-by-Step Solution

### Prerequisites

Ensure you have the following installed:
```bash
sudo apt install -y cmake gcc pkg-config \
  libcjson-dev libglib2.0-dev libgnutls28-dev libgpgme-dev \
  libical-dev libpq-dev postgresql-server-dev-all xsltproc \
  libbsd-dev libcurl4-gnutls-dev libgcrypt-dev libhiredis-dev \
  libnet1-dev libpaho-mqtt-dev libpcap-dev libssh-dev \
  libxml2-dev uuid-dev
```

### Step 1: Build and Install gvm-libs v22.30.0

The newer gvmd requires gvm-libs >= 22.30, but Debian packages only provide 22.29.3.

```bash
cd /home/jake/decian-dev
git clone https://github.com/greenbone/gvm-libs.git --branch v22.30.0 --depth 1
cd gvm-libs
mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr ..
make -j$(nproc)
sudo make install
sudo ldconfig
```

**Verify installation:**
```bash
pkg-config --modversion libgvm_base
# Should output: 22.30.0~git-bbfc391-HEAD (or similar)
```

### Step 2: Build and Install gvmd v26.6.0 with Agent Support

```bash
cd /home/jake/decian-dev
git clone https://github.com/greenbone/gvmd.git gvmd-full
cd gvmd-full
git checkout v26.6.0
mkdir -p build && cd build

# Configure with agent features ENABLED
export PKG_CONFIG_PATH=/usr/lib64/pkgconfig:$PKG_CONFIG_PATH
cmake -DENABLE_AGENTS=1 \
      -DENABLE_CONTAINER_SCANNING=1 \
      -DCMAKE_INSTALL_PREFIX=/usr \
      ..

make -j$(nproc)
```

**Stop the running gvmd service before installing:**
```bash
sudo systemctl stop gvmd.service
sudo make install
sudo ldconfig
```

**Verify agent features are enabled:**
```bash
gvmd --version
```

Expected output should include:
```
Greenbone Vulnerability Manager 26.6.0~git-28b9428c0-HEAD
Agent scanning and management enabled
Container scanning enabled
```

**Restart gvmd:**
```bash
sudo systemctl daemon-reload
sudo systemctl start gvmd.service
```

### Step 3: Build and Install GSA Frontend v26.2.0

The GSA frontend needs Node.js 22 to build.

#### Install Node.js 22 (via nvm)
```bash
# Install Node.js 22 if not already installed
source ~/.config/nvm/nvm.sh
nvm install 22
nvm use 22
npm install -g yarn
```

#### Build GSA
```bash
cd /home/jake/decian-dev
git clone https://github.com/greenbone/gsa.git
cd gsa
git checkout v26.2.0

# Install dependencies (this may show peer dependency warnings - that's okay)
bash -c "source ~/.config/nvm/nvm.sh && nvm use 22 && yarn install"

# Add missing testing dependencies
bash -c "source ~/.config/nvm/nvm.sh && nvm use 22 && yarn add -D @testing-library/dom terser"

# Build the frontend (takes ~4 minutes)
bash -c "source ~/.config/nvm/nvm.sh && nvm use 22 && yarn build"
```

#### Deploy the New Frontend
```bash
# Backup old GSA web files
sudo mv /usr/share/gvm/gsad/web /usr/share/gvm/gsad/web.old

# Install new GSA v26.2.0 frontend
sudo cp -r build /usr/share/gvm/gsad/web

# Restart GSA daemon
sudo systemctl restart gsad.service
```

### Step 4: Verify Installation

**Check backend version and features:**
```bash
gvmd --version
```

Should show:
- Version: 26.6.0
- "Agent scanning and management enabled"
- "Container scanning enabled"

**Access the web interface:**
Open your browser and navigate to: `http://localhost:9392`

You should now see agent management options in the web UI.

---

## Why Agent Features Were Not Showing Initially

### Compile-Time vs Runtime Configuration

The key insight is that agent support in GVM is a **compile-time feature**, not a runtime configuration option:

1. **Compile-time flags** (`ENABLE_AGENTS`, `ENABLE_CONTAINER_SCANNING`) control whether the code for these features is even included in the binary
2. The Debian/Kali package maintainers built gvmd with these flags set to `0` (disabled)
3. No amount of configuration changes could enable features that weren't compiled into the binary

### Frontend-Backend Version Compatibility

Even with the backend features enabled, the old GSA frontend (v24.5.4) lacked the UI components to display:
- Agent management pages
- Agent group configuration
- Container scanning options
- Related navigation menu items

The frontend needed to be upgraded to v26.x to match the backend capabilities.

---

## Current Status and Known Limitations

### What's Working Now
✅ Agent scanning and management features enabled in backend (gvmd v26.6.0)
✅ Container scanning features enabled in backend
✅ GSA frontend updated to v26.2.0 with agent UI components
✅ Backend and frontend versions are compatible
✅ System accessible at http://localhost:9392
✅ Agent Owner setting configured (admin user)

### Known Limitations

⚠️ **Agent Controller Service Required (Enterprise Feature)**

After investigation, we discovered that full agent functionality requires an **Agent Controller service**, which appears to be a Greenbone Enterprise/commercial component that is not available in the open-source Community Edition.

**What's Missing:**
- **Agent Controller Service**: A separate HTTP/HTTPS service that manages agents (similar to how OSPd manages OpenVAS scanners)
- **Agent Controller Scanner**: A scanner entry (type 7 - `agent-controller`) that points to the Agent Controller service
- **Agent Installer Data**: Agent installation packages and configurations served by the Agent Controller

**Current Impact:**
- Agent Installer tab shows no data (requires agent controller connection)
- Agent Groups creation shows "no agent controller to select from" (requires an agent-controller scanner)
- Agents tab may show "Unknown command" errors for some GMP commands

**What Has Been Configured:**
- ✅ Agent Owner user setting (UUID `1ee1f106-8b2e-461c-b426-7f5d76001b29`) set to admin user
- ✅ Backend compiled with `ENABLE_AGENTS=1` and `ENABLE_CONTAINER_SCANNING=1`
- ✅ gvm-libs 22.30.0 includes agent controller client library
- ✅ Frontend UI components for agent management are present

⚠️ **Customer management features are not yet fully functional**

Customer management may also be part of the Enterprise feature set and requires similar infrastructure.

---

## Component Versions

| Component | Old Version | New Version | Source |
|-----------|-------------|-------------|--------|
| gvm-libs | 22.29.3 | **22.30.0** | Built from source |
| gvmd | 26.2.1 (no agents) | **26.6.0** (agents enabled) | Built from source |
| GSA | 24.5.4 | **26.2.0** | Built from source |

---

## Configuration Files Modified

### GSA Daemon Service Override
**File:** `/etc/systemd/system/gsad.service.d/override.conf`

```ini
[Service]
ExecStart=
ExecStart=/usr/sbin/gsad --foreground --listen 127.0.0.1 --port 9392 --munix-socket=/run/gvmd/gvmd.sock --http-only
```

This configuration:
- Points GSA to the gvmd Unix socket at `/run/gvmd/gvmd.sock`
- Serves HTTP only (suitable for localhost, use HTTPS for production)
- Listens on port 9392

---

## Troubleshooting

### If agent features still don't show:
1. Verify backend has features enabled: `gvmd --version`
2. Check frontend was properly deployed: `ls -la /usr/share/gvm/gsad/web/`
3. Clear browser cache or try incognito mode
4. Check gsad logs: `sudo journalctl -u gsad -n 50`
5. Check gvmd logs: `sudo journalctl -u gvmd -n 50`

### If build fails:
- Ensure all development dependencies are installed
- Check that pkg-config can find gvm-libs: `pkg-config --list-all | grep libgvm`
- Verify Node.js version for GSA build: `node --version` (should be v22.x)

---

## References

- gvmd source: https://github.com/greenbone/gvmd
- gvm-libs source: https://github.com/greenbone/gvm-libs
- GSA source: https://github.com/greenbone/gsa
- gvmd installation docs: `/home/jake/decian-dev/gvmd-decian/INSTALL.md`

---

## Understanding Agent Architecture

### How Agent Management Works in GVM

The agent management system in GVM is designed as a three-tier architecture:

```
┌─────────────────┐
│   GSA (Web UI)  │ ← Frontend displays agent management UI
└────────┬────────┘
         │ GMP Protocol
         ▼
┌─────────────────┐
│      gvmd       │ ← Backend processes agent commands
└────────┬────────┘
         │ HTTP/HTTPS + gvm-libs agent_controller client
         ▼
┌─────────────────┐
│ Agent Controller│ ← External service (Enterprise/Commercial)
│    Service      │   Manages actual agents, installers, configs
└─────────────────┘
```

**Key Components:**

1. **gvmd (Backend)**:
   - Compiled with `ENABLE_AGENTS=1`
   - Uses gvm-libs agent_controller client library
   - Stores scanner entries (type 7 = agent-controller) pointing to Agent Controller services

2. **Agent Controller Service** (Missing - Enterprise Feature):
   - Separate HTTP/HTTPS service
   - Provides REST API for managing agents
   - Serves agent installers
   - Tracks agent status and heartbeats
   - Similar role to how OSPd works for OpenVAS scanners

3. **Scanners Table**:
   - Must have at least one scanner of type `SCANNER_TYPE_AGENT_CONTROLLER` (type 7)
   - Scanner entry contains: host, port, protocol (http/https)
   - Optional: CA cert, client cert, API key for authentication

### What We Have Accomplished

Even without the Agent Controller service, we've successfully:

1. ✅ **Enabled Agent Support in Backend**: gvmd v26.6.0 compiled with agent features
2. ✅ **Upgraded Frontend**: GSA v26.2.0 includes all agent UI components
3. ✅ **Installed Client Library**: gvm-libs 22.30.0 with agent_controller client code
4. ✅ **Set Agent Owner**: Database setting configured for admin user

### For Enterprise/Production Use

To fully utilize agent features, you would need:
- Access to Greenbone Enterprise Edition or commercial Agent Controller service
- Agent Controller service running on a network-accessible host
- Scanner entry configured with Agent Controller connection details
- Agents installed on target systems reporting to the Agent Controller

---

## Next Steps

### Completed
✅ Set up agent owner user setting
✅ Investigated agent controller requirements
✅ Documented Enterprise feature limitations

### For Future Reference

If you gain access to a Greenbone Agent Controller service:

1. **Create Agent Controller Scanner**:
```bash
# Via GMP command or web UI
# Scanner Type: 7 (agent-controller)
# Host: <agent-controller-host>
# Port: <agent-controller-port>
```

2. **Configure Authentication** (see `docs/integration-authentication.md`):
   - mTLS (client certificates), or
   - API Key authentication

3. **Test Agent Synchronization**:
   - Agents should appear in the Agents tab
   - Agent groups can be created
   - Agent installers will be available

---

*Documentation created: 2025-11-05*
*Documentation updated: 2025-11-05*
*System: Debian-based Kali Linux*
