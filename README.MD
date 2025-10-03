[![HACS Validation](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/hacs.yml/badge.svg)](https://github.com/EHylands/ha-qolsys-panel/actions/workflows/hacs.yml)

# Qolsys Panel – HACS Custom Integration

This is a custom integration for **Qolsys Panels** (such as IQ Panel 2/4), allowing local pairing and control via Home Assistant.

---

## 🧩 Installation

This integration is not yet part of the official HACS store. You must add it manually as a custom repository.

### Steps:

1. Open Home Assistant.
2. Navigate to: **HACS → Integrations → Menu (⋮) → Custom repositories**.
3. Add the GitHub URL of this integration repository.
4. Set the category to **Integration**.
5. Once added, install the integration like any other HACS component.

🔗 [How to add a custom repository in HACS](https://www.hacs.xyz/docs/faq/custom_repositories/)

---

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

4. When prompted for the pairing method, choose:  
   **Automatic Panel Discovery and Pairing**

---

### 🔐 2. Pairing with an Existing Signed Client Certificate (PKI)

If you already have a **signed client certificate**, you can use it for secure, authenticated pairing with the panel.

**Steps:** (coming soon or to be documented based on implementation)

---

## ✨ Functionality Highlights

| Category               | Feature                             | Status |
|------------------------|--------------------------------------|--------|
| **Panel**              | Diagnostic Sensors                   | ✅     |
| **Partition**          | Arming Status                        | ✅     |
|                        | Alarm State                          | ✅     |
|                        | Home Instant Arming                 | ✅     |
|                        | Set Exit Sounds                      | ✅     |
|                        | Disarm Photos                        | 🛠️     |
| **Zones**              | Sensor Status                        | ✅     |
|                        | Tamper State                         | ✅     |
|                        | Battery Level                        | ✅     |
|                        | Signal Level                         | ✅     |
| **Z-Wave Dimmers**     | Light Status and Level Control       | ✅     |
| **Z-Wave Devices**     | Battery Level                        | ✅     |
|                        | Pairing Status                       | ✅     |
|                        | Node Status                          | ✅     |
|                        | Control Generic Devices              | 🔜     |
| **Z-Wave Door Locks**  |                                      | 🛠️     |
| **Z-Wave Thermostats** |                                      | 🛠️     |
| **Z-Wave Garage Doors**|                                      | 🛠️     |
| **Z-Wave Outlets**     |                                      | 🛠️     |
