#!/usr/bin/env python3
"""
Startup script voor LeRobot op Raspberry Pi.
Dit script wordt automatisch uitgevoerd bij reboot via crontab.
"""

import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path


def log(message: str) -> None:
    """Print bericht met timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def check_devices() -> bool:
    """
    Controleer of USB serial devices beschikbaar zijn.
    Returns: True als devices gevonden zijn.
    """
    dev_dir = Path("/dev")
    
    # Zoek naar tty_* symlinks
    tty_devices = list(dev_dir.glob("tty_*"))
    
    if tty_devices:
        log(f"✅ Gevonden {len(tty_devices)} USB serial device(s):")
        for dev in sorted(tty_devices):
            log(f"   - {dev.name}")
        return True
    else:
        log("⚠️  Geen USB serial devices gevonden")
        return False


def initialize_lerobot() -> None:
    """
    Initialiseer LeRobot systeem.
    Voeg hier je specifieke initialisatie code toe.
    """
    log("🤖 Initialiseer LeRobot systeem...")
    
    # Check of lerobot package beschikbaar is
    try:
        import lerobot
        log(f"✅ LeRobot package geladen (versie: {lerobot.__version__ if hasattr(lerobot, '__version__') else 'unknown'})")
    except ImportError as e:
        log(f"❌ LeRobot package niet gevonden: {e}")
        return
    
    log("✅ LeRobot systeem geïnitialiseerd")


def start_teleoperation() -> None:
    """
    Start LeRobot teleoperation in de achtergrond.
    
    Gebruikt /dev/tty_follower en /dev/tty_leader als standaard,
    of leest opgeslagen keuze uit ~/.lerobot_teleop_config
    """
    log("🎮 Start teleoperation...")
    
    config_file = Path.home() / ".lerobot_teleop_config"
    
    # Initialiseer variabelen
    follower_port = None
    leader_port = None
    follower_type = None
    leader_type = None
    follower_id = None
    leader_id = None
    use_saved_config = False
    
    # Check of er een opgeslagen configuratie is
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                lines = f.read().strip().split('\n')
                if len(lines) >= 2:
                    saved_follower = lines[0].strip()
                    saved_leader = lines[1].strip()
                    
                    # Valideer dat de devices nog bestaan
                    if Path(saved_follower).exists() and Path(saved_leader).exists():
                        log(f"📋 Gebruik opgeslagen configuratie:")
                        log(f"   Follower: {saved_follower}")
                        log(f"   Leader: {saved_leader}")
                        
                        # Parse device info uit saved paths
                        follower_name = Path(saved_follower).name.replace("tty_", "")
                        leader_name = Path(saved_leader).name.replace("tty_", "")
                        
                        follower_parts = follower_name.split("_")
                        leader_parts = leader_name.split("_")
                        
                        if len(follower_parts) >= 3 and len(leader_parts) >= 3:
                            follower_type = follower_parts[-1]
                            follower_id = "_".join(follower_parts[:-2])
                            leader_type = leader_parts[-1]
                            leader_id = "_".join(leader_parts[:-2])
                            
                            follower_port = saved_follower
                            leader_port = saved_leader
                            use_saved_config = True
                        else:
                            log("⚠️  Kon opgeslagen configuratie niet parsen, gebruik standaard")
                            config_file.unlink()  # Verwijder ongeldige config
                    else:
                        log("⚠️  Opgeslagen devices niet gevonden, gebruik standaard")
                        config_file.unlink()
        except Exception as e:
            log(f"⚠️  Fout bij lezen configuratie: {e}")
            if config_file.exists():
                config_file.unlink()
    
    # Als er geen geldige saved config is, gebruik standaard /dev/tty_follower en /dev/tty_leader
    if not use_saved_config:
        log("📋 Gebruik standaard devices: /dev/tty_follower en /dev/tty_leader")
        
        follower_port = "/dev/tty_follower"
        leader_port = "/dev/tty_leader"
        
        # Check of devices bestaan
        if not Path(follower_port).exists():
            log(f"⚠️  Geen follower device gevonden: {follower_port}")
            return
        
        if not Path(leader_port).exists():
            log(f"⚠️  Geen leader device gevonden: {leader_port}")
            return
        
        # Standaard: SO-101 robots zonder specifieke ID
        follower_type = "so101"
        follower_id = "default"
        leader_type = "so101"
        leader_id = "default"
    
    # Teleoperation commando (gebruik symbolic links voor stabiliteit)
    cmd = [
        "lerobot-teleoperate",
        f"--robot.type={follower_type}_follower",
        f"--robot.port={follower_port}",
        f"--robot.id={follower_id}",
        f"--teleop.type={leader_type}_leader",
        f"--teleop.port={leader_port}",
        f"--teleop.id={leader_id}"
    ]
    
    try:
        log(f"   Command: {' '.join(cmd)}")
        # Start als achtergrond proces
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log(f"✅ Teleoperation gestart (PID: {process.pid})")
        log(f"   Follower: {follower_port} (ID: {follower_id}, Type: {follower_type})")
        log(f"   Leader: {leader_port} (ID: {leader_id}, Type: {leader_type})")
        
    except Exception as e:
        log(f"❌ Fout bij starten teleoperation: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Main startup functie."""
    log("=" * 60)
    log("🚀 LeRobot Startup Script")
    log("=" * 60)
    
    # Wacht even tot systeem volledig opgestart is
    log("⏳ Wacht 10 seconden voor systeem initialisatie...")
    time.sleep(10)
    
    # Check USB devices
    devices_found = check_devices()
    
    if not devices_found:
        log("⚠️  Start zonder USB devices")
    
    # Initialiseer LeRobot
    try:
        initialize_lerobot()
    except Exception as e:
        log(f"❌ Fout tijdens initialisatie: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Start teleoperation
    if devices_found:
        try:
            start_teleoperation()
        except Exception as e:
            log(f"❌ Fout bij starten teleoperation: {e}")
            import traceback
            traceback.print_exc()
    else:
        log("⚠️  Skip teleoperation (geen devices)")
    
    log("=" * 60)
    log("✅ Startup compleet")
    log("=" * 60)


if __name__ == "__main__":
    main()
