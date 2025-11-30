#!/usr/bin/env python3
"""
Interactief script om een robot/teleop paar te selecteren en teleoperation te starten.
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict


def get_devices() -> Dict[str, List[Tuple[str, Path, str, str]]]:
    """
    Scan /dev voor leader en follower devices.
    
    Returns:
        Dict met 'leaders' en 'followers' keys, elk met een lijst van tuples:
        (nice_name, port_path, type, symlink_name)
    """
    dev_dir = Path("/dev")
    
    leaders = []
    followers = []
    
    # Zoek alle tty_* symlinks
    for device_link in sorted(dev_dir.glob("tty_*")):
        name = device_link.name
        
        # Parse naam: tty_<name>_<role>_<type>
        if not name.startswith("tty_"):
            continue
            
        parts = name.replace("tty_", "").split("_")
        if len(parts) < 3:
            continue
        
        robot_type = parts[-1]  # Laatste deel
        role = parts[-2]  # Voorlaatste deel
        nice_name = "_".join(parts[:-2])  # Rest is de nice name
        
        port_path = device_link.resolve()
        
        if role == "leader":
            leaders.append((nice_name, port_path, robot_type, name))
        elif role == "follower":
            followers.append((nice_name, port_path, robot_type, name))
    
    return {"leaders": leaders, "followers": followers}


def print_device_list(devices: List[Tuple[str, Path, str, str]], role: str) -> None:
    """Print een mooie lijst van devices."""
    if not devices:
        print(f"  Geen {role}s gevonden")
        return
    
    print(f"\n  {role.upper()}S:")
    for idx, (nice_name, port_path, robot_type, symlink) in enumerate(devices, 1):
        print(f"    [{idx}] {nice_name} ({robot_type}) -> {port_path}")


def select_device(devices: List[Tuple[str, Path, str, str]], role: str) -> Tuple[str, Path, str, str]:
    """
    Laat gebruiker een device selecteren uit de lijst.
    
    Returns:
        Tuple van (nice_name, port_path, type, symlink_name)
    """
    if not devices:
        print(f"\n❌ Geen {role}s gevonden!")
        sys.exit(1)
    
    if len(devices) == 1:
        device = devices[0]
        print(f"\n✅ Automatisch geselecteerd: {device[0]} ({device[2]})")
        return device
    
    print(f"\n🤖 Selecteer een {role}:")
    for idx, (nice_name, port_path, robot_type, symlink) in enumerate(devices, 1):
        print(f"  [{idx}] {nice_name} ({robot_type})")
    
    while True:
        try:
            choice = input(f"\nKies {role} [1-{len(devices)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                selected = devices[idx]
                print(f"✅ Geselecteerd: {selected[0]} ({selected[2]})")
                return selected
            else:
                print(f"⚠️  Kies een nummer tussen 1 en {len(devices)}")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Geannuleerd")
            sys.exit(0)


def start_teleoperation(
    follower: Tuple[str, Path, str, str],
    leader: Tuple[str, Path, str, str]
) -> None:
    """
    Start teleoperation met geselecteerde devices.
    
    Args:
        follower: (nice_name, port_path, type, symlink_name)
        leader: (nice_name, port_path, type, symlink_name)
    """
    follower_id, follower_port, follower_type, follower_symlink = follower
    leader_id, leader_port, leader_type, leader_symlink = leader
    
    print("\n" + "=" * 60)
    print("🎮 START TELEOPERATION")
    print("=" * 60)
    print(f"  Follower: {follower_id} ({follower_type})")
    print(f"    Port: {follower_port}")
    print(f"    Link: /dev/{follower_symlink}")
    print()
    print(f"  Leader: {leader_id} ({leader_type})")
    print(f"    Port: {leader_port}")
    print(f"    Link: /dev/{leader_symlink}")
    print("=" * 60)
    
    # Bouw commando
    cmd = [
        "lerobot-teleoperate",
        f"--robot.type={follower_type}_follower",
        f"--robot.port={follower_port}",
        f"--robot.id={follower_id}",
        f"--teleop.type={leader_type}_leader",
        f"--teleop.port={leader_port}",
        f"--teleop.id={leader_id}"
    ]
    
    print(f"\n💻 Command:")
    print(f"  {' '.join(cmd)}")
    print()
    
    # Vraag bevestiging
    confirm = input("Start teleoperation? [Y/n]: ").strip().lower()
    if confirm and confirm not in ['y', 'yes', 'j', 'ja']:
        print("❌ Geannuleerd")
        sys.exit(0)
    
    print("\n🚀 Starten...")
    
    try:
        # Start teleoperation (foreground, zodat gebruiker output ziet)
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  Teleoperation gestopt door gebruiker")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Fout bij uitvoeren teleoperation (exit code: {e.returncode})")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Onverwachte fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main functie."""
    print("=" * 60)
    print("🤖 LeRobot Teleoperation Selector")
    print("=" * 60)
    
    # Scan devices
    print("\n🔍 Scannen naar devices...")
    devices = get_devices()
    
    leaders = devices["leaders"]
    followers = devices["followers"]
    
    print(f"\n✅ Gevonden: {len(followers)} follower(s), {len(leaders)} leader(s)")
    print_device_list(followers, "follower")
    print_device_list(leaders, "leader")
    
    if not followers or not leaders:
        print("\n❌ Je hebt minimaal 1 follower én 1 leader nodig!")
        print("\n💡 Tip: Controleer of:")
        print("  - USB devices zijn aangesloten")
        print("  - Udev rules zijn geïnstalleerd (/etc/udev/rules.d/99-lerobot.rules)")
        print("  - Devices zijn gemapped in mapping.csv")
        sys.exit(1)
    
    print("\n" + "-" * 60)
    
    # Selecteer follower
    follower = select_device(followers, "follower")
    
    # Selecteer leader
    leader = select_device(leaders, "leader")
    
    # Start teleoperation
    start_teleoperation(follower, leader)


if __name__ == "__main__":
    main()
