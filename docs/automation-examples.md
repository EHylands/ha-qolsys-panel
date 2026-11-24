# 💡 Automation Examples

[← Back to the README](../README.MD)

Paste an example into a new automation's YAML editor (**Settings → Automations & scenes → Create automation → ⋮ → Edit in YAML**). Then replace the entity IDs with your own: they're listed under **Settings → Devices & services → Qolsys Panel → Entities**.

### Make the panel speak

Announce on the panel when the garage door has been open for 10 minutes. The panel speaks plain text only, so use `media_player.play_media` with `media_content_type: text`. `tts.speak` won't work.

```yaml
alias: "Panel: garage door left open"
triggers:
  - trigger: state
    entity_id: cover.garage_door
    to: "open"
    for: "00:10:00"
actions:
  - action: media_player.play_media
    target:
      entity_id: media_player.panel_qolsys_tts_player
    data:
      media_content_type: text
      media_content_id: "The garage door has been open for 10 minutes."
```

### Send a Peek In snapshot when the doorbell rings

When the panel reports a doorbell press, capture a Peek In picture and send it to your phone. **Enable Peek In Picture** must be on in the integration options. It's on by default.

```yaml
alias: "Doorbell: send a Peek In snapshot"
triggers:
  - trigger: state
    entity_id: binary_sensor.panel_doorbell
    to: "on"
actions:
  - action: qolsys_panel.update_picture_peek_in
    data:
      config_entry_id: "{{ config_entry_id('image.panel_peek_in_picture') }}"
  # The picture arrives from the panel a moment later.
  - wait_for_trigger:
      - trigger: state
        entity_id: image.panel_peek_in_picture
    timeout: "00:00:30"
    continue_on_timeout: false
  - action: notify.mobile_app_your_phone
    data:
      message: "Someone is at the door."
      data:
        image: /api/image_proxy/image.panel_peek_in_picture
```

### Arm away when everyone leaves

Arm the partition when nobody is home. Turning on **Force Arm** first bypasses zones left open, such as a window, instead of failing to arm. The switch turns itself off after the partition arms.

```yaml
alias: "Alarm: arm away when everyone leaves"
triggers:
  - trigger: numeric_state
    entity_id: zone.home
    below: 1
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.partition1_home_force_arm
  - action: alarm_control_panel.alarm_arm_away
    target:
      entity_id: alarm_control_panel.partition1_home
    # Only needed when "User Code required to Arm" is on in the integration options.
    # data:
    #   code: !secret alarm_code
```

### Toggle lights from a scene controller button

Double-tap a Z-Wave Central Scene button to toggle a light. Each button is an event entity. Its state changes on every press, and the `event_type` attribute says which kind of press it was.

```yaml
alias: "Remote: double-tap toggles the living room lights"
triggers:
  - trigger: state
    entity_id: event.living_room_remote_scene_1
    not_from: unavailable
conditions:
  - condition: state
    entity_id: event.living_room_remote_scene_1
    attribute: event_type
    state: double_tap
actions:
  - action: light.toggle
    target:
      entity_id: light.living_room
```
