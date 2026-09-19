# Vendored `qolsys_controller`

Upstream: [EHylands/QolsysController](https://github.com/EHylands/QolsysController),
PyPI package `qolsys-controller`, **version 1.8.0** (1.7.1 vendored 2026-09-07; the 1.7.2 and 1.8.0 changes applied
2026-09-12 from the PyPI wheels, see "Upstream versions" below), taken from the
`qolsys_controller-1.7.1-py3-none-any.whl` wheel published on PyPI.
License: MIT, kept verbatim at `qolsys_controller/LICENSE`.

## Why it is vendored

The September 2026 security audit of this integration found seven defects whose
fix lives inside the library rather than in the integration: the file modes of
the PKI material (H2), the pairing server accepting any client (H1), the
`@SECLEVEL=0` cipher string (M3), the missing observer notification on the
`RECONNECTING` transition (M2), blocking filesystem I/O on the event loop (M5),
cleartext user codes (H3, L5), the unauthenticated MQTT-bridge disarm path (M8),
and the commented-out safety-zone guard (L1). Shipping a patched copy is the
only way to get those fixes onto a panel that guards a house without waiting on
an upstream release, so the PyPI dependency was dropped from
`manifest.json` and the code moved here.

Keep the copy close to upstream: every deviation is listed below, and a future
upgrade should re-apply exactly this list on top of the new upstream source.

## Changes made while vendoring (no behavior change)

1. **Import rewrite.** 60 modules used absolute imports (`from
   qolsys_controller.x import y`). Rewritten to package-relative imports
   (`from .x import y`, `from ..x import y`) so the package works at its new
   dotted path `custom_components.qolsys_panel.vendor.qolsys_controller`.
2. **`mqtt_bridge/broker.py`**: the amqtt plugin is selected by dotted path
   string, which moved with the package. Now built from `__package__`.
3. `qolsys_controller-1.7.1.dist-info/` was not copied; the LICENSE from it is
   kept at `qolsys_controller/LICENSE`.
4. The vendored tree is excluded from this repo's ruff and mypy configuration
   (`pyproject.toml`, `mypy.ini`): it is upstream code in upstream style, and
   linting it would bury the audit fixes in restyling noise.

## Dependencies

The library's own requirements are now declared directly in
`custom_components/qolsys_panel/manifest.json`: `aiofiles`, `aiomqtt`,
`paho-mqtt` (aiomqtt's transport), `cryptography`, `passlib` and `zeroconf`.

`mqtt_bridge/broker.py` and `mqtt_bridge/auth_plugin.py` additionally need
`amqtt`, which upstream ships as the optional `bridge` extra. It is deliberately
NOT declared: the broker is disabled and the modules that import `amqtt` are
imported lazily (`broker.py::_import_amqtt`) or not at all. `auth_plugin.py` is
therefore the one vendored module that cannot be imported, which is expected -
only amqtt's plugin loader ever loads it, by dotted path.

`passlib` must stay declared even though the new `user_codes.py` uses stdlib
`hashlib`: `mqtt_bridge/bridge.py` imports it at module scope and `controller.py`
imports that module.

**Decision on deleting `mqtt_bridge/` (review N8).** 1,240 lines that cannot run,
containing a disarm path, is dead weight in code that guards a house, and
deleting the package (plus the `MqttBridge` import in `controller.py`) would
close M8 by construction rather than by three guards, and drop `passlib` from
the manifest. Kept for now: it is a large deviation to re-apply at every
re-vendor, and the three guards (both settings pinned off with a startup check,
the broker certificate pinned, the disarm path requiring a valid code) are
tested. Revisit at the next upstream re-vendor, when the deviation can be judged
against the new upstream layout.

## Audit fixes applied to the vendored copy

Each entry names the audit ID; see the repository CHANGELOG for the matching
commit.

### H2 - PKI material was world readable (0o644) and went into every backup

New module `qolsys_controller/file_permissions.py`: `set_mode`, `secure_file`
(0o600), `secure_directory` (0o700) and `secure_tree` (a repair pass).

- `pki.py`: chmod the per-MAC subkeys directory 0o700 and the `.key`, `.cer`,
  `.csr` and MQTT-bridge key/cert files 0o600 right after writing them; new
  `QolsysPKI.secure_existing_material()`.
- `pairing_server.py`: same for the `.secure` client certificate and the
  `.qolsys` pinned CA.
- `settings.py::check_config_directory`: chmod the pki and mqtt_bridge
  directories 0o700.
- `controller.py::config_task`: run `secure_existing_material()` on startup so
  installations paired before this fix are repaired, not just new ones.

`secure_tree` and `set_mode` refuse to act through a symlink (review N1), so a
link planted in the PKI directory cannot make the startup repair pass chmod a
file elsewhere.

The three PKI files are written and then chmodded, so each exists at the umask
default for an instant. Left that way on purpose (review N9): the containing
directory is 0700 by then, so nothing can traverse to the file during the
window, and reworking three `aiofiles` writes into `os.open(..., 0o600)` buys
nothing that the directory mode does not already give.

Residual: the private key is still stored unencrypted (PKCS#8, `NoEncryption`).
Encrypting it needs a passphrase kept outside `/config`, which changes the
pairing format and cannot be validated without a panel. A `/config` backup taken
by a user who can already read files as the Home Assistant user still contains
the key.

### H3 / L5 - user codes were stored in cleartext and compared with `==`

New module `qolsys_controller/user_codes.py`: PBKDF2-HMAC-SHA256, 210,000
iterations, 16-byte random salt, stored as
`pbkdf2_sha256$<iterations>$<salt>$<hash>`, verified with
`hmac.compare_digest`.

- `users.py`: `QolsysUser.user_code` becomes `user_code_hash`; the cleartext
  code is never held in memory.
- `panel.py::read_users_file`: chmods users.conf 0o600, rejects malformed rows
  with `QolsysConfigError` (an unguarded `user.get()` used to store `None`, and
  a stored `None` then matched a `None` lookup), hashes any hand-written
  cleartext `user_code` and rewrites the file in place through a temporary file
  that is chmodded before the rename.
- `panel.py::check_user`: constant-time verification, and it checks every user
  instead of returning at the first match, so the answer does not depend on
  position in the list.
- `commands/panel.py`: `check_user` now derives a KDF, so both call sites run it
  with `asyncio.to_thread` rather than on the event loop.

A malformed row is logged, counted (`QolsysPanel.users_file_malformed_rows`) and
skipped rather than raising (review N4): raising failed the config entry and took
every entity with it, and losing the zone sensors and the alarm state because of
a typo in one code is worse than losing that one code. A file that is not
readable JSON still raises. A file with a malformed row is never rewritten, so
the line the operator has to fix is still there afterwards.

Residual: a 4-digit code has 10,000 possibilities, so a stolen users.conf is
still brute-forceable offline; the hash costs an attacker roughly 25 ms per
guess and removes the cleartext. The panel still receives only a user id, so
this validation is enforced by Home Assistant and never by the panel (audit C1).

### M8 - the disabled MQTT bridge carried an unauthenticated disarm and CERT_NONE TLS

- `mqtt_bridge/client.py`: the broker TLS context was
  `create_default_context()` with `check_hostname = False` and
  `verify_mode = CERT_NONE`, so any host could impersonate the broker. It now
  pins the bridge certificate written by `create_mqtt_bridge_certificates`
  (`CERT_REQUIRED`, `cafile=mqtt_bridge.cer`), hostname checking still off
  because that certificate has no SAN.
- `mqtt_bridge/client.py::_cmd_disarm`: refuses a payload with no `user_code`
  and validates the code against the panel database before disarming, whatever
  `check_user_code_on_disarm` says. Two new error responses,
  `user_code_required` and `invalid_user_code`.
- `settings.py`: `_mqtt_bridge_enabled` now defaults to `False`.

The integration additionally pins both bridge switches off in
`async_setup_entry` and refuses to start if they do not hold.

Residual: none of this path is exercised by the integration and it cannot be
tested without a broker, so the changes are defence in depth behind a bridge
that stays off.

### H1 - the pairing server authenticated no one

**Not fixed in full, and deliberately so.** The audit's preferred fix
(`verify_mode = CERT_REQUIRED` with the panel CA pinned) needs something to pin
before pairing has happened, and the vendor protocol offers nothing: the panel
presents no client certificate, and the CA it will use is exactly what pairing
fetches. Requiring a client certificate would make every pairing fail, and
inventing a challenge the panel does not implement is not something that can be
designed without a panel to test against. `verify_mode` therefore stays
`ssl.CERT_NONE`, with the reason written at the call site.

What was implemented instead, all in `pairing_server.py`:

- **One peer per window.** The first address that connects owns the pairing
  window; a connection from any other address is refused for the rest of it. A
  retry from the same address is still allowed, because a panel that drops
  mid-exchange must be able to come back.
- **Expected-address check.** When `settings.panel_ip` is already known, only
  that address may pair at all. That covers both the existing-PKI re-pair path
  and, since review B2, the common case: DHCP/zeroconf discovery stores the
  panel's address before the menu is shown, and the config flow now hands it to
  the pairing server. It is empty only on a manual add with no discovery, where
  the check stays off.
- **The peer is logged**, at warning level, with a "confirm this is your panel"
  note, so the address is in the log the operator reads after pairing.
- **The listener is bound only for the pairing window**: new `_close_listener()`
  closes the accepting socket the moment pairing completes, fails or times out,
  instead of leaving it bound until the controller stops the server.
- **The material is validated before it is written**: the signed client
  certificate must parse as X.509 and must carry the public key from our own
  CSR (`_validate_client_certificate`), and the `.qolsys` file that becomes the
  pinned trust anchor must parse as X.509 (`_validate_panel_ca`), which is
  logged with its subject, issuer and serial. Whether the client certificate
  verifies against that CA is logged as a warning rather than enforced: a panel
  that signs through an intermediate would fail the check, and breaking pairing
  on an unverifiable guess is worse than reporting it.

The config flow now tells the user to pair on a trusted network and to check the
logged address (`strings.json` **and** `translations/en.json` - Home Assistant
serves a custom integration's config-flow text from the translation file, so a
notice that lands only in `strings.json` is never shown; `test_translations.py`
keeps the two identical).

**Residual risk.** An attacker already on the LAN who connects during the
pairing window, before the panel does, still becomes the device Home Assistant
pairs with, unless the panel IP was known in advance - which it now is whenever
discovery found the panel. The certificate validation does not help against this
attacker: winning the race lets them sign our own CSR with their own CA, which
passes every check, and their chain is self-consistent so the CA cross-check
logs nothing. The expected-address check is the control that stops it. `settings.pairing_timeout`
is left at 180 s: shortening it trades a smaller window against a user who
cannot reach the wall panel in time, and that tradeoff cannot be measured
without the hardware. Pair on a quiet network, then check the pairing address in
the log and the stored `panel_ip`.

### M2 - the CONNECTED -> RECONNECTING transition emitted no notification

`controller.py::set_controller_state` now calls `notify_panel_status_update()`
itself, after the new state is committed and the condition released, and the two
callers that used to notify by hand no longer do: the one in the `finally` block
ran while the state still read CONNECTED, and entities went unavailable only
because a deferred state write happened to land after the flip.

Entities are unavailable whenever the controller is not CONNECTED, so this makes
"the panel is unreachable" deterministic instead of a scheduling accident.

`observable.py` gained a per-observer guard (review N6): notification now
happens on the reconnect path, where `run_supervised` catches only
`CancelledError`, so an observer that raised would stop the controller
reconnecting while entities sat on their last written state. Each callback is
delivered inside a try/except that logs and continues.

### M5 - blocking filesystem I/O on the event loop

`controller.py::config_task` called `settings.check_config_directory()`
(four `is_dir()` probes, up to four `mkdir(parents=True)` and eight `resolve()`
calls) and `pki.auto_discover_pki()` (`os.scandir`) directly on the loop, right
next to a `read_users_file` that was correctly wrapped. Both now run through
`asyncio.to_thread`.

### M3 - TLS to the panel ran at security level 0

`controller.py::mqtt_open_transport_task` now sets
`DEFAULT:@SECLEVEL=1` instead of `DEFAULT:@SECLEVEL=0`. The rest of that context
is unchanged and was already sound: `CERT_REQUIRED` against the pinned `.qolsys`
CA, `minimum_version = TLSv1_2`, and `tls_insecure=True` only turning off
hostname checking.

Residual: not verified against a physical panel. SECLEVEL=1 still accepts the
SHA-1/2048-bit chain these panels are documented to present; if a panel does
fail the handshake, the OpenSSL error appears as a QolsysSslError in the log and
the exact message should be recorded here before the level is lowered again.

### L1 - the open-safety-zone arming guard was commented out

`commands/panel.py::arm` built `open_safety_zones` and then used it only inside
a comment, so the panel armed with an open smoke, CO or water sensor and no
warning anywhere. The guard is restored: open safety zones raise
`QolsysZoneBypassError`, which the integration already surfaces as
"Zone bypass required".

Residual: a safety zone genuinely cannot be bypassed on these panels, so this
is the behavior the code intended; if a specific panel disagrees the error names
the zones, which is enough to tell.

### Residual: disarming from Home Assistant needs `users.conf` to exist

Added after review (residual 9). The C1 default means a fresh install refuses
every disarm until the operator creates `config/qolsys_panel/users.conf`, and
`read_users_file` returns quietly when the file is absent, so nothing used to
explain it. Failing closed is right for an alarm and the physical panel is
unaffected, but it is the change most likely to be experienced as "the
integration broke", so the integration now logs a warning and raises a repair
issue naming the file (`__init__.py::_async_report_user_codes`), and the README
says it in the user-codes section.

### Residual: arming now fails with an open safety zone

The L1 guard is a behavior change users meet in normal life: a wet water sensor
or a smoke detector in fault stops arming, where earlier versions armed silently.
The error names the zones, and the README's alarm-entity description says so.


## 2026-09-07 follow-up: SECLEVEL back to 0 (M3 reverted)

The first pairing against a real IQ Panel failed the post-pairing TLS connection with `[SSL: CA_MD_TOO_WEAK] ca md too weak` at `load_cert_chain`: the panel's CA uses a digest that OpenSSL security level 1 rejects. `controller.py` is back to `DEFAULT:@SECLEVEL=0`, as upstream ships. Residual: level 0 permits weak signature digests and small keys in general; what protects this connection is the pin to the panel's own CA saved at pairing, the TLS 1.2 floor, and the LAN-only path. A firmware that moves the panel CA to SHA-256 would allow level 1 again.

## Upstream versions taken after the initial vendoring

- **1.7.2 to 1.8.0 (applied 2026-09-12):** `commands/panel.py` gains
  `change_master_volume_level` (0 to 15) and `change_doorbell_volume_level`
  (0 to 7), `panel.py` reads the `PANEL_VOLUME` and `VOLUME_DOORBELL` settings,
  and `automation_zwave/device.py` stops after the first matching service per
  endpoint and adds a default outlet service for an endpoint it has no service
  for. **Not taken:** 1.7.2's two new database tables (`table_yale_auth_ids.py`,
  `table_ime_data.py`, registered in `database/db.py`). Upstream declares them
  implemented with a single `_id` column and `_report_new_columns = True`, so
  every row the panel sends would log four "New column found ... Please Report"
  warnings at each load. This fork keeps those two tables in
  `UNUSED_TABLE_URIS` (skipped at debug level, 1.7.8), which reads nothing from
  them either. Revisit if upstream fills in their columns.
