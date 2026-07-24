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

- **Alarm Control Panel** (`alarm_control_panel`): one per partition; reports the arming status and alarm state, and supports arming (home, away, night) and disarming.
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
