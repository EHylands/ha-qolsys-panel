[![HACS Validation](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/hacs.yml/badge.svg)](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/hacs.yml)

# Qolsys Panel – HACS Custom Integration

This is a custom integration for **Qolsys Panels** (such as IQ Panel 2+/4), allowing local pairing and control via Home Assistant.

## 🧩 Installation

This integration is not yet part of the official HACS store. You must add it manually as a custom repository.

### Steps:

1. Open Home Assistant.
2. Navigate to: **HACS → Integrations → Menu (⋮) → Custom repositories**.
3. Add the GitHub URL of this integration repository.
4. Set the category to **Integration**.
5. Once added, install the integration like any other HACS component.

🔗 [How to add a custom repository in HACS](https://www.hacs.xyz/docs/faq/custom_repositories/)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=EHylands&repository=ha-qolsys-panel&category=Integration+)

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

## ✅ Supported Devices

Any **Qolsys Panel** that can be paired with an **IQ Remote**:

- IQ Panel 2+
- IQ Panel 4
- IQ 4 Hub
- IQ 4 NS (IQ Installer app)
- IQ Hub
- IQ Pro (IQ Installer app)

## 📦 Provided Entities

The following entities are provided by this integration:

- Alarm Control Panel
- Binary Sensor
- Climate
- Light
- Lock
- Media Player (TTS)
- Sensor
- Siren
- Switch
- Scene
- Valve
- Weather

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

| Automation Devices| Z-Wave | PowerG | Alarm.com |
|-----------------|--------|--------|-------|
| Door Lock        | ✅     | ✅     | ❌    |
| Energy Clamp     | ✅     | ❌     | ❌    |
| External Siren   | 🛠️     | ❌     | ❌    |
| Garage Door      | 🛠️     | ❌     | ✅    |
| Lights           | ✅     | 🛠️     | ✅    |
| Smart Outlet     | 🛠️     | ❌     | ❌    |
| Thermometer      | ✅     | ❌     | ❌    |
| Thermostat       | ✅     | ❌     | ❌    |
| Water Valve      | 🛠️     | ❌     | ❌    |
