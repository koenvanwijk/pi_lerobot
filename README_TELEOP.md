# LeRobot Teleoperation

## Overzicht

Dit systeem gebruikt een **webserver** voor teleoperation control:

1. **`webserver.py`** - Web interface voor remote control (start automatisch bij reboot + auto-start teleoperation)
2. **`select_teleop.py`** - Interactieve device selectie (voor handmatig gebruik)

## 🌐 Web Control Interface (Aanbevolen)

### Auto-start bij reboot

**Bij reboot gebeurt automatisch:**
1. Webserver start (na 5 seconden delay)
2. Devices worden gedetecteerd
3. **Teleoperation start automatisch** als devices beschikbaar zijn
4. Web interface is beschikbaar op poort 5000

⚡ **Plug & Play**: Sluit USB devices aan en reboot → teleoperation draait automatisch!

### Toegang

Na reboot is de webserver automatisch beschikbaar op:
- **Lokaal**: http://localhost:5000
- **Netwerk**: http://[RASPBERRY_PI_IP]:5000

### Features
- 🚀 Auto-start teleoperation bij boot
- ▶️ Start/Stop teleoperation met één klik
- 📊 Real-time status monitoring
- 🤖 Device info (Follower & Leader)
- 🔄 Auto-refresh elke 5 seconden

### Standaard gedrag

De webserver gebruikt automatisch:
- `/dev/tty_follower` (standaard: eerste follower uit mapping.csv)
- `/dev/tty_leader` (standaard: eerste leader uit mapping.csv)
- Type: `so101` (standaard robot type)

```bash
# Commando dat automatisch uitgevoerd wordt bij boot:
lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port=/dev/tty_follower \
  --robot.id=default \
  --teleop.type=so101_leader \
  --teleop.port=/dev/tty_leader \
  --teleop.id=default
```

## 🛠️ Handmatig gebruik

### Specifieke robot kiezen (select_teleop.py)

Wanneer je meerdere robots hebt, gebruik je `select_teleop.py`:

```bash
./select_teleop.py
```

Dit script:
1. **Toont** alle aangesloten followers en leaders
2. **Laat je kiezen** welke je wilt gebruiken
3. **Slaat de keuze op** in `~/.lerobot_teleop_config`
4. **Start teleoperation** met je gekozen devices

**De opgeslagen keuze blijft actief na reboot!**

### Terug naar standaard

Om terug te gaan naar de standaard devices:

```bash
./select_teleop.py --reset
```

Dit verwijdert de opgeslagen configuratie en de webserver gebruikt weer de standaard `/dev/tty_follower` en `/dev/tty_leader`.

## Voorbeelden

### Voorbeeld 1: Standaard gebruik (1 robot)

Als je maar 1 follower en 1 leader hebt:
- Na reboot: automatisch gestart met standaard devices
- Geen actie nodig!

### Voorbeeld 2: Meerdere robots

Je hebt 3 followers (white_12, blue, pink) en 2 leaders (black, yellow):

```bash
$ ./select_teleop.py

============================================================
🤖 LeRobot Teleoperation Selector
============================================================

🔍 Scannen naar devices...

✅ Gevonden: 3 follower(s), 2 leader(s)

  FOLLOWERS:
    [1] white_12 (so101)
    [2] blue (so101)
    [3] pink (so101)

  LEADERS:
    [1] black (so101)
    [2] yellow (so101)

------------------------------------------------------------

🤖 Selecteer een follower:
  [1] white_12 (so101)
  [2] blue (so101)
  [3] pink (so101)

Kies follower [1-3]: 2
✅ Geselecteerd: blue (so101)

🤖 Selecteer een leader:
  [1] black (so101)
  [2] yellow (so101)

Kies leader [1-2]: 1
✅ Geselecteerd: black (so101)

============================================================
🎮 START TELEOPERATION
============================================================
  Follower: blue (so101)
    Port: /dev/tty_blue_follower_so101 -> /dev/ttyACM1

  Leader: black (so101)
    Port: /dev/tty_black_leader_so101 -> /dev/ttyACM3
============================================================

💾 Configuratie opgeslagen in /home/pi/.lerobot_teleop_config
   Deze keuze wordt bij reboot hergebruikt door startup.py

Start teleoperation? [Y/n]: y

🚀 Starten...
```

Na reboot gebruikt `startup.py` automatisch blue + black!

### Voorbeeld 3: Terug naar standaard

```bash
$ ./select_teleop.py --reset

✅ Configuratie gereset!
   Startup.py zal nu standaard /dev/tty_follower en /dev/tty_leader gebruiken
```

## Technische details

### Udev symlinks

De udev rules maken voor elk device meerdere symlinks:

```
# Specifieke link:
/dev/tty_white_12_follower_so101 -> /dev/ttyACM0

# Generieke link (eerste van elk type):
/dev/tty_follower -> /dev/ttyACM0
/dev/tty_leader -> /dev/ttyACM3
```

### Configuratie bestand

`~/.lerobot_teleop_config` bevat twee regels:
```
/dev/tty_blue_follower_so101
/dev/tty_black_leader_so101
```

### Startup flow

```
startup.py start
  ↓
Bestaat ~/.lerobot_teleop_config?
  ↓ JA              ↓ NEE
  ↓                 ↓
Devices bestaan?    Gebruik standaard:
  ↓ JA    ↓ NEE    /dev/tty_follower
  ↓       ↓        /dev/tty_leader
Gebruik Reset      Type: so101
saved   config     ID: default
config    ↓
  ↓       ↓
  └───────┴─→ Start teleoperation
```

## Tips

- ✅ Symbolic links zijn **stabiel**: blijven werken ongeacht USB poort
- ✅ `select_teleop.py` draait in **foreground**: je ziet alle output
- ✅ `startup.py` draait in **background**: output gaat naar `~/startup.log`
- ✅ Gebruik **Ctrl+C** om teleoperation te stoppen
- ✅ De configuratie is **persistent**: blijft na reboot
