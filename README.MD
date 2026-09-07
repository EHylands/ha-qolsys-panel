## About this fork

This is Lukas Pleva's audited fork of [EHylands/ha-qolsys-panel](https://github.com/EHylands/ha-qolsys-panel), taken at upstream version 1.6.1; this fork is version 1.7.0. It exists because every integration that holds a login or can act on the house gets a line-by-line audit before it runs in his Home Assistant, and the fixes live here rather than upstream.

**Why it was forked.** This integration arms and disarms the house alarm. As shipped, disarming from Home Assistant required no code by default and the panel itself never checks one, the keypad's private key was written world-readable into the config folder, pairing accepted any device on the network, and user codes were stored in clear.

**What is different.** Disarming now requires a user code that Home Assistant checks (constant-time, against a salted PBKDF2 hash) before any command is sent, and existing installs are migrated to that setting. The `qolsys-controller` library is vendored and hardened: key material is written owner-only (0600 files in 0700 directories, with a repair pass for older installs), user codes are hashed at rest, the pairing window is fenced (one peer, the panel's known address enforced, the returned certificate checked against our own key, the listener alive only during the window), the dormant MQTT bridge is pinned off, the TLS security level raised, the reconnect state reaches entities deterministically so they go unavailable rather than freezing, and the safety-zone arming guard is restored. Tests grew from 296 to 365, run against Home Assistant 2026.9.1. An independent review then found two more issues, both fixed, including the panel-address check being inert on the discovery path. Residual risks are listed in `custom_components/qolsys_panel/vendor/VENDORED.md`; the main one: the disarm code is enforced by Home Assistant, not by the panel. Fixes are not sent upstream; upstream is unchanged by this fork.

**How it is kept current.** A weekly job merges upstream's new commits onto a branch, runs this fork's tests, reviews the diff, and only then pushes; a merge conflict or a failing test stops it. The fork is installed through HACS as a custom repository, so Home Assistant offers each new version as an update.

**Where the detail is.** CHANGELOG.md and custom_components/qolsys_panel/vendor/VENDORED.md record every change by audit finding.

---

# HA Qolsys Panel

[![Build](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/release.yml/badge.svg)](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/release.yml)

This is a HACS custom integration for **Qolsys Panels** (such as IQ Panel 2+/4), allowing local pairing and control via Home Assistant.

## 🧩 Installation

This integration is now part of the official HACS store. 

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=EHylands&repository=ha-qolsys-panel&category=Integration+)

### Manuel Install Steps:

1. Open Home Assistant.
2. Navigate to: **HACS → Integrations → Menu (⋮) → Custom repositories**.
3. Add the GitHub URL of this integration repository.
4. Set the category to **Integration**.
5. Once added, install the integration like any other HACS component.

🔗 [How to add a custom repository in HACS](https://www.hacs.xyz/docs/faq/custom_repositories/)

## ⚙️ Configuration

You can pair with your Qolsys Panel using one of the following two methods:

### 🔍 1. Panel Autodiscovery and Pairing

**Requirements:**

- Home Assistant server and Qolsys Panel must be on the **same network subnet** for automatic mDNS pairing to work.
- You must have the **installer code** for your Qolsys Panel.

**Steps:**

1. On your Qolsys Panel, access the IQ Remote pairing page:  
   `Settings → Advanced Settings → Installation → Devices → WI-FI Devices → IQ Remote Devices`

2. In Home Assistant, go to:  
   `Settings → Devices & Services → Integrations → Add Integration`

3. Search for **Qolsys Panel**.

4. When prompted for the pairing method, choose:  **Automatic Panel Discovery and Pairing**

### 🔐 2. Pairing with an Existing Signed Client Certificate (PKI)

If you already have a **signed client certificate**, you can use it to securely pair with your Qolsys panel.  

With this method, **Home Assistant and the Qolsys Panel do not need to be on the same subnet**, since it doesn’t rely on mDNS discovery.

**Requirements:**

- Qolsys Panel IP address
- A valid PKI folder located at:  
  `/homeassistant/qolsys_panel/pki/[***random_mac***]/`

  Example contents of the PKI folder (`f2163e3a5fb1` is the random_mac):

  ```
  /homeassistant/qolsys_panel/pki/f2163e3a5fb1/
    ├── f2163e3a5fb1.key
    ├── f2163e3a5fb1.cer
    ├── f2163e3a5fb1.csr
    ├── f2163e3a5fb1.qolsys
    ├── f2163e3a5fb1.secure
  ```

**Steps:**

1. **In Home Assistant**:
   - Navigate to:  
`Settings → Devices & Services → Integrations → Add Integration`

2. Search for **Qolsys Panel**.

3. When prompted for the pairing method, choose: **Use Existing PKI**

4. Enter your **Qolsys Panel IP**

5. Select the appropriate PKI folder from the dropdown menu (it will list folders from `/homeassistant/qolsys_panel/pki/`)

## 🔢 User Codes, Arming and Disarming

**Disarming requires a user code, and Home Assistant is what checks it.**

- **Disarm code: required by default.** The alarm entity asks for a code before it
  disarms, and the integration refuses the command if the code is missing or is not
  in your `users.conf`. Existing installations are migrated to this setting on
  upgrade; you can turn it off under **Settings > Devices & Services > Qolsys Panel
  > Configure**, which is not recommended.
- **Arm code: optional, off by default.** Arming home/away/night without a code is
  the normal behavior of an alarm panel. The same **Configure** page has an
  *Enable or Disable User Code* option for arming; when it is on, arming validates
  the code exactly the way disarming does.

### Where the codes live: `config/qolsys_panel/users.conf`

The panel does not expose its user database, so the integration keeps its own
list. Create `users.conf` in the integration's config directory with one entry
per user:

```json
[
  { "id": 1, "user_code": "1234" },
  { "id": 2, "user_code": "5678" }
]
```

`id` is the panel user id reported to the panel with the command; `user_code` is
the code you will type in Home Assistant.

**Codes are not kept in cleartext.** On the next start the integration replaces
each `user_code` with a salted PBKDF2-SHA256 hash and rewrites the file, owner
readable only (`0600`):

```json
[
  { "id": 1, "user_code_hash": "pbkdf2_sha256$210000$..." }
]
```

Codes are then verified by a constant-time comparison against that hash. To
change or add a code, write the `user_code` form again and restart.

**If `users.conf` does not exist, every disarm from Home Assistant is refused.**
The keypad still appears and every code comes back as "Invalid user code",
because there is nothing to check it against. Home Assistant raises a repair
issue and a log warning saying exactly that. The physical panel is unaffected,
and you can turn the check off again on the integration's **Configure** page.

**A malformed entry is skipped, not fatal.** The row is logged, counted and
reported as a repair issue, and the rest of the file still loads: a typo in one
code must not take the zone sensors and the alarm state offline with it. The
file is left exactly as written in that case (so the entry you need to fix is
still there), which also means cleartext codes in it are not replaced by hashes
until the malformed rows are fixed. A `users.conf` that is not valid JSON at all
*does* fail the integration setup, because no codes could be read.

Note that a 4-digit code has only 10,000 possibilities, so the hash slows an
attacker down rather than making a stolen file safe. Keep `users.conf` out of
version control and out of shared backups, and prefer codes you do not reuse on
the front-door lock.

### ⚠️ The panel does not check the code, Home Assistant does

The panel disarms on the authority of the paired IQ Remote certificate. The MQTT
disarm message carries a user *ID*, never the code itself, so there is no second
line of defence behind Home Assistant:

- Anyone who can call `alarm_control_panel.alarm_disarm` **with a valid code from
  your `users.conf`** disarms the alarm. That includes every Home Assistant user
  account regardless of admin status, every automation and script, anything holding
  a long-lived access token, and any other custom integration in the same process.
- Treat Home Assistant administrator access as equivalent to knowing the alarm code.
- Do not expose this Home Assistant instance to the internet without multi-factor
  authentication.

## 🛠️ PKI Auto-Discovery and Pairing Troubleshooting

If pairing is not working, please verify the following:

1. **Same subnet**: Ensure the Home Assistant server and Qolsys Panel are on the same subnet.

2. **mDNS filtering**: Check your network equipment for mDNS filtering or storm-control features. Some Wi-Fi systems and managed switches may block or limit mDNS traffic, which can prevent device discovery.

3. **Pairing service advertisement**: Verify that the pairing service is being advertised. While the integration is in pairing mode, use a discovery tool (for example, the **Discovery** app on iPhone) to confirm that the `.http NsdPairService` service is visible on the network.

4. **Key-exchange server interface**: Review the Home Assistant logs when starting pairing. Confirm that the key-exchange server is listening on the expected IP address and network interface. If the wrong interface is selected, you can configure the default network adapter in:
   `Settings → System → Network → Network Adapter`

## ✅ Supported Devices

Any **Qolsys Panel** that can be paired with an **IQ Remote**:

- IQ Panel 2+
- IQ Panel 4
- IQ 4 Hub
- IQ 4 NS (IQ Installer app)
- IQ Hub
- IQ Panel 5
- IQ Pro (IQ Installer app)

## 📦 Supported Functionality

The integration emulates an IQ Remote and exposes the panel's capabilities to Home Assistant through the entities and actions below, grouped by what each represents on the panel.

### Partitions

- **Alarm Control Panel** (`alarm_control_panel`): one per partition; reports the arming status and alarm state, and supports arming (home, away, night) and disarming. **Arming fails while a safety zone is open** (smoke, CO or water): those zones cannot be bypassed, so the action returns "Zone bypass required" naming the zones, rather than arming a system that cannot protect them. Earlier versions armed silently in that case.
- **Binary sensors** (`binary_sensor`): Exit Sounds, Entry Delays and Quick Exit status, plus dedicated Fire, Police, CO and Auxiliary alarm-active sensors.
- **Switches** (`switch`): toggle Exit Sounds and Entry Delay, and set the Arm Stay Instant (Arm Home with no exit delay) and Arm Stay Silent Disarming modifiers for the partition.
- **Sensor** (`sensor`): the last error reported by the partition.

### Panel

- **Diagnostic binary sensors** (`binary_sensor`): AC status, tamper, battery status, communication failure, Z-Wave controller, secure arming, auto stay, auto arm stay, auto bypass and Control4.
- **Doorbell** and **Chime** (`binary_sensor`): pulse when the panel reports a doorbell press or a chime.
- **Media Player** (`media_player`): text-to-speech; use the standard speak/`tts` actions to make the panel talk.
- **Scenes** (`scene`): activate scenes defined on the panel.
- **Weather** (`weather`): the panel's weather forecast.

### Zones (security sensors)

- **Binary sensor** (`binary_sensor`): open/closed (or motion, etc.) status for each zone, plus per-zone Unreachable, Tamper, Battery and AC-status sensors.
- **Sensors** (`sensor`): Latest and Average signal strength (dBm) and Battery Level/Voltage, plus Temperature and Light on supported PowerG devices.

### Automation devices (Z-Wave, PowerG, Zigbee)

Depending on the device type, the integration creates the matching platform entity:

- **Lock** (`lock`): door locks.
- **Light** (`light`) and **Switch** (`switch`): dimmers and outlets.
- **Climate** (`climate`): thermostats.
- **Cover** (`cover`) and **Valve** (`valve`): controllable openings.
- **Siren** (`siren`).
- **Sensors** (`sensor`): battery level, generic sensor readings and energy-meter values.
- **Binary sensor** (`binary_sensor`): device reachability/status.

### Actions

All actions target a partition's `alarm_control_panel` entity:

| Action | Description | Options |
|--------|-------------|---------|
| `qolsys_panel.trigger_police` | Trigger a Police alarm on the panel | `silent` (boolean) |
| `qolsys_panel.trigger_auxilliary` | Trigger an Auxiliary alarm on the panel | `silent` (boolean) |
| `qolsys_panel.trigger_fire` | Trigger a Fire alarm on the panel | — |
| `qolsys_panel.quick_exit` | Open a door while Armed-Stay without triggering an alarm | `duration` (seconds) |

## 🔄 Data Updates

This integration is **local push**. It maintains a persistent local MQTT connection to the panel (by emulating an IQ Remote) and receives state changes in real time as the panel reports them within moments of a change. The integration does **not** poll the panel on an interval. If the connection drops it reconnects automatically.

## ⚠️ Known Limitations

- **IQ Remote emulation** — The integration communicates with the panel by emulating an IQ Remote device. Only features and devices the panel exposes to IQ Remotes can be monitored or controlled

## 🔧 Removing the Integration

This integration follows the standard Home Assistant integration removal process — **no extra steps are required**.

To remove an integration instance from Home Assistant:

1. Go to **Settings** > **Devices & Services**.
2. Find and select the **integration card** you want to remove.
3. From the list of devices, locate the specific **integration instance**.
4. Click the **three dots menu** (⋮) next to the entry.
5. Select **Delete**.

The integration will be cleanly removed from your system.

## ✨ Functionality Highlights

| Category               | Feature                              | Status |
|------------------------|--------------------------------------|--------|
| **Panel**              | Diagnostic Sensors                   | ✅     |
|                        | Panel Scenes                         | ✅     |
|                        | Speak Command                        | ✅     |
|                        | Weather Forecast                     | ✅     |
| **Partition**          | Arming Status and Alarm State        | ✅     |
|                        | Home Instant Arming                  | ✅     |
|                        | Home Silent Disarming (Firmware 4.6.1)| ✅     |
|                        | Trigger Alarm                         | ✅     |
|                        | Enable or Disable User Code           | ✅     |
|                        | Set Exit Sounds and Entry Delay       | ✅     |
| **Zones**              | Sensor Status                        | ✅     |
|                        | Tamper State                         | ✅     |
|                        | Battery Level                        | ✅     |
|                        | Temperature (supported PowerG device)| ✅     |
|                        | Light (supported PowerG device)      | ✅     |
|                        | Average and Latest dBm               | ✅     |

| Automation Devices| Z-Wave | PowerG | Zigbee | Alarm.com |
|-----------------|--------|--------|-------|-------|
| Door Lock        | ✅     | ✅     | ✅    | ❌    |
| Energy Clamp     | ✅     | ❌     | ❌    | ❌    |
| External Siren   | ✅     | ❌     | ❌    | ❌    |
| Garage Door      | ✅     | ❌     | ❌    | ✅    |
| Light            | ✅     | ✅     | ✅    | ✅    |
| Smart Outlet     | 🛠️     | ❌     | ❌    | ❌    |
| Thermometer      | ✅     | ❌     | ❌    | ❌    |
| Thermostat       | ✅     | ❌     | ❌    | ❌    |
| Water Valve      | 🛠️     | ❌     | ❌    | ❌    |

🛠️ = partially supported or untested
