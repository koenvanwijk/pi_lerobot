#!/usr/bin/env python3
"""
LeRobot Web Control Server
Webserver voor remote control van teleoperation.
"""

import sys
import subprocess
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from flask import Flask, render_template_string, jsonify
import threading


class RobotState:
    """Globale state voor robot control."""
    def __init__(self):
        self.teleop_process: Optional[subprocess.Popen] = None
        self.teleop_mode: str = "stopped"
        self.devices_available: bool = False
        self.follower_port: Optional[str] = None
        self.leader_port: Optional[str] = None
        self.follower_type: Optional[str] = None
        self.leader_type: Optional[str] = None
        self.follower_id: Optional[str] = None
        self.leader_id: Optional[str] = None
    
    def is_running(self) -> bool:
        """Check of teleoperation proces draait."""
        if self.teleop_process is None:
            return False
        return self.teleop_process.poll() is None
    
    def refresh_state(self):
        """Refresh state van system."""
        # Check devices
        dev_dir = Path("/dev")
        tty_devices = list(dev_dir.glob("tty_*"))
        self.devices_available = len(tty_devices) > 0
        
        # Load config
        if not self.follower_port:
            self.load_device_config()
    
    def load_device_config(self) -> bool:
        """Laad device configuratie."""
        config_file = Path.home() / ".lerobot_teleop_config"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    lines = f.read().strip().split('\n')
                    if len(lines) >= 2:
                        saved_follower = lines[0].strip()
                        saved_leader = lines[1].strip()
                        
                        if Path(saved_follower).exists() and Path(saved_leader).exists():
                            follower_name = Path(saved_follower).name.replace("tty_", "")
                            leader_name = Path(saved_leader).name.replace("tty_", "")
                            
                            follower_parts = follower_name.split("_")
                            leader_parts = leader_name.split("_")
                            
                            if len(follower_parts) >= 3 and len(leader_parts) >= 3:
                                self.follower_type = follower_parts[-1]
                                self.follower_id = "_".join(follower_parts[:-2])
                                self.leader_type = leader_parts[-1]
                                self.leader_id = "_".join(leader_parts[:-2])
                                self.follower_port = saved_follower
                                self.leader_port = saved_leader
                                return True
            except Exception:
                pass
        
        # Defaults
        self.follower_port = "/dev/tty_follower"
        self.leader_port = "/dev/tty_leader"
        self.follower_type = "so101"
        self.follower_id = "default"
        self.leader_type = "so101"
        self.leader_id = "default"
        
        return Path(self.follower_port).exists() and Path(self.leader_port).exists()

state = RobotState()


def log(message: str) -> None:
    """Print bericht met timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def start_teleoperation() -> bool:
    """Start LeRobot teleoperation."""
    if state.is_running():
        log("⚠️  Teleoperation draait al")
        return False
    
    log("🎮 Start teleoperation...")
    
    if not state.follower_port or not state.leader_port:
        if not state.load_device_config():
            log("❌ Geen geldige device configuratie")
            return False
    
    # Copy config values
    follower_port = state.follower_port
    leader_port = state.leader_port
    follower_type = state.follower_type
    leader_type = state.leader_type
    follower_id = state.follower_id
    leader_id = state.leader_id
    
    # Build command outside lock - use conda run (works in subprocess)
    cmd = [
        "conda", "run", "-n", "lerobot", "--no-capture-output",
        "lerobot-teleoperate",
        f"--robot.type={follower_type}_follower",
        f"--robot.port={follower_port}",
        f"--robot.id={follower_id}",
        f"--teleop.type={leader_type}_leader",
        f"--teleop.port={leader_port}",
        f"--teleop.id={leader_id}"
    ]
    
    try:
        log(f"   Follower: {follower_port} ({follower_type})")
        log(f"   Leader: {leader_port} ({leader_type})")
        
        teleop_log_file = Path.home() / "teleoperation.log"
        log(f"   Output → {teleop_log_file}")
        
        # Open log file in append mode (blijft open voor subprocess)
        log_file = open(teleop_log_file, 'a')
        log_file.write("\n" + "=" * 60 + "\n")
        log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting teleoperation\n")
        log_file.write(f"Follower: {follower_port} ({follower_type}/{follower_id})\n")
        log_file.write(f"Leader: {leader_port} ({leader_type}/{leader_id})\n")
        log_file.write("=" * 60 + "\n")
        log_file.flush()
        
        # Start subprocess OUTSIDE lock to avoid blocking
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Update state
        state.teleop_process = process
        state.teleop_mode = "teleoperation"
        
        log(f"✅ Teleoperation gestart (PID: {process.pid})")
        return True
        
    except Exception as e:
        import traceback
        log(f"❌ Fout bij starten teleoperation: {e}")
        log(f"   Traceback: {traceback.format_exc()}")
        state.teleop_process = None
        state.teleop_mode = "stopped"
        return False


def stop_teleoperation() -> bool:
    """Stop het teleoperation proces."""
    if not state.is_running():
        log("⚠️  Teleoperation draait niet")
        state.teleop_mode = "stopped"
        return False
    
    log("🛑 Stop teleoperation...")
    
    try:
        state.teleop_process.terminate()
        
        for _ in range(50):
            if state.teleop_process.poll() is not None:
                break
            time.sleep(0.1)
        
        if state.teleop_process.poll() is None:
            log("⚠️  Process reageert niet, force kill...")
            state.teleop_process.kill()
            state.teleop_process.wait()
        
        log("✅ Teleoperation gestopt")
        state.teleop_process = None
        state.teleop_mode = "stopped"
        return True
        
    except Exception as e:
        log(f"❌ Fout bij stoppen teleoperation: {e}")
        return False


# Flask web application
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LeRobot Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .status-card {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 5px solid #667eea;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .status-row:last-child { border-bottom: none; }
        .status-label {
            font-weight: 600;
            color: #555;
        }
        .status-value {
            font-family: 'Courier New', monospace;
            color: #333;
            background: white;
            padding: 5px 10px;
            border-radius: 5px;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .status-running {
            background: #d4edda;
            color: #155724;
        }
        .status-stopped {
            background: #f8d7da;
            color: #721c24;
        }
        .status-available {
            background: #d1ecf1;
            color: #0c5460;
        }
        .button-group {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        button {
            padding: 15px 30px;
            font-size: 1.1em;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        button:active {
            transform: translateY(0);
        }
        .btn-start {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        .btn-stop {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }
        .btn-refresh {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }
        .device-info {
            background: white;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            border: 2px solid #e0e0e0;
        }
        .device-info h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .device-detail {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            font-size: 0.9em;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #999;
            font-size: 0.85em;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .loading {
            animation: pulse 1.5s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 LeRobot Control</h1>
        <p class="subtitle">Raspberry Pi Teleoperation Controller</p>
        
        <div class="status-card">
            <div class="status-row">
                <span class="status-label">Status:</span>
                <span class="status-badge" id="mode-badge">Loading...</span>
            </div>
            <div class="status-row">
                <span class="status-label">Devices:</span>
                <span class="status-badge status-available" id="devices-badge">Checking...</span>
            </div>
            <div class="status-row">
                <span class="status-label">Process PID:</span>
                <span class="status-value" id="pid-value">-</span>
            </div>
        </div>
        
        <div id="device-container"></div>
        
        <div class="button-group">
            <button class="btn-start" onclick="startTeleoperation()" id="btn-start">
                ▶️ Start Teleoperation
            </button>
            <button class="btn-stop" onclick="stopTeleoperation()" id="btn-stop">
                ⏹️ Stop Teleoperation
            </button>
            <button class="btn-refresh" onclick="updateStatus()">
                🔄 Refresh Status
            </button>
        </div>
        
        <div class="footer">
            Last updated: <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const modeBadge = document.getElementById('mode-badge');
                    modeBadge.textContent = data.mode.toUpperCase();
                    modeBadge.className = 'status-badge ' + (data.running ? 'status-running' : 'status-stopped');
                    
                    const devicesBadge = document.getElementById('devices-badge');
                    devicesBadge.textContent = data.devices_available ? 'Available ✓' : 'Not Found ✗';
                    devicesBadge.className = 'status-badge ' + (data.devices_available ? 'status-available' : 'status-stopped');
                    
                    document.getElementById('pid-value').textContent = data.pid || 'Not running';
                    
                    if (data.follower_port && data.leader_port) {
                        document.getElementById('device-container').innerHTML = `
                            <div class="device-info">
                                <h3>🤖 Follower (Robot)</h3>
                                <div class="device-detail">
                                    <span>Port:</span>
                                    <span><code>${data.follower_port}</code></span>
                                </div>
                                <div class="device-detail">
                                    <span>Type:</span>
                                    <span><code>${data.follower_type}</code></span>
                                </div>
                                <div class="device-detail">
                                    <span>ID:</span>
                                    <span><code>${data.follower_id}</code></span>
                                </div>
                            </div>
                            <div class="device-info">
                                <h3>🎮 Leader (Controller)</h3>
                                <div class="device-detail">
                                    <span>Port:</span>
                                    <span><code>${data.leader_port}</code></span>
                                </div>
                                <div class="device-detail">
                                    <span>Type:</span>
                                    <span><code>${data.leader_type}</code></span>
                                </div>
                                <div class="device-detail">
                                    <span>ID:</span>
                                    <span><code>${data.leader_id}</code></span>
                                </div>
                            </div>
                        `;
                    }
                    
                    document.getElementById('btn-start').disabled = data.running || !data.devices_available;
                    document.getElementById('btn-stop').disabled = !data.running;
                    
                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        }
        
        function startTeleoperation() {
            if (!confirm('Start teleoperation?')) return;
            
            const btn = document.getElementById('btn-start');
            btn.disabled = true;
            btn.classList.add('loading');
            
            fetch('/api/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ Teleoperation started!');
                    } else {
                        alert('❌ Failed to start: ' + data.message);
                    }
                    updateStatus();
                })
                .catch(error => {
                    alert('❌ Error: ' + error);
                    btn.disabled = false;
                })
                .finally(() => {
                    btn.classList.remove('loading');
                });
        }
        
        function stopTeleoperation() {
            if (!confirm('Stop teleoperation?')) return;
            
            const btn = document.getElementById('btn-stop');
            btn.disabled = true;
            btn.classList.add('loading');
            
            fetch('/api/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ Teleoperation stopped!');
                    } else {
                        alert('❌ Failed to stop: ' + data.message);
                    }
                    updateStatus();
                })
                .catch(error => {
                    alert('❌ Error: ' + error);
                    btn.disabled = false;
                })
                .finally(() => {
                    btn.classList.remove('loading');
                });
        }
        
        setInterval(updateStatus, 5000);
        updateStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Web interface homepage."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def api_status():
    """Get current robot status."""
    state.refresh_state()
    return jsonify({
        'running': state.is_running(),
        'mode': state.teleop_mode,
        'devices_available': state.devices_available,
        'pid': state.teleop_process.pid if state.is_running() else None,
        'follower_port': state.follower_port,
        'leader_port': state.leader_port,
        'follower_type': state.follower_type,
        'leader_type': state.leader_type,
        'follower_id': state.follower_id,
        'leader_id': state.leader_id,
    })


@app.route('/api/start', methods=['POST'])
def api_start():
    """Start teleoperation."""
    success = start_teleoperation()
    return jsonify({
        'success': success,
        'message': 'Teleoperation started' if success else 'Failed to start teleoperation'
    })


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop teleoperation."""
    success = stop_teleoperation()
    return jsonify({
        'success': success,
        'message': 'Teleoperation stopped' if success else 'Failed to stop teleoperation'
    })


def auto_start_thread():
    """Separate thread voor auto-start van teleoperation."""
    # Wacht even voor systeem stabiliteit (vooral bij boot)
    log("⏳ Wacht 5 seconden voor systeem initialisatie...")
    time.sleep(5)
    
    # Initial state refresh
    state.refresh_state()
    
    if state.devices_available:
        log("✅ USB devices beschikbaar")
        
        # Auto-start teleoperation als devices beschikbaar zijn
        log("🎮 Auto-start teleoperation...")
        time.sleep(2)  # Extra delay voor device stabiliteit
        
        if start_teleoperation():
            log("✅ Teleoperation automatisch gestart")
        else:
            log("⚠️  Kon teleoperation niet automatisch starten")
    else:
        log("⚠️  Geen USB devices gevonden - teleoperation niet gestart")
        log("   💡 Sluit devices aan en start handmatig via web interface")


def main():
    """Main entry point."""
    log("=" * 60)
    log("🌐 LeRobot Web Control Server")
    log("=" * 60)
    
    # Start auto-start in aparte thread zodat webserver niet blokkeert
    auto_start = threading.Thread(target=auto_start_thread, daemon=True)
    auto_start.start()
    
    log("🚀 Webserver beschikbaar op http://0.0.0.0:5000")
    log("   Lokaal: http://localhost:5000")
    log("   Netwerk: http://[IP]:5000")
    log("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        log("\n🛑 Shutdown signal ontvangen")
        if state.is_running():
            stop_teleoperation()
        sys.exit(0)


if __name__ == "__main__":
    main()
