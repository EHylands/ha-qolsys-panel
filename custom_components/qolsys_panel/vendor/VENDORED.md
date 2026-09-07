# Vendored `qolsys_controller`

Upstream: [EHylands/QolsysController](https://github.com/EHylands/QolsysController),
PyPI package `qolsys-controller`, **version 1.7.1**, taken from the
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
imported lazily (`broker.py::_import_amqtt`) or not at all.

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

Residual: a 4-digit code has 10,000 possibilities, so a stolen users.conf is
still brute-forceable offline; the hash costs an attacker roughly 25 ms per
guess and removes the cleartext. The panel still receives only a user id, so
this validation is enforced by Home Assistant and never by the panel (audit C1).
