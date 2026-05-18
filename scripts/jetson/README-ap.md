# KiSTI in-car WiFi access point

Step 1 of the iPhone-as-interface architecture (see prior advisory). Turns
the Jetson into a self-contained WiFi network the phone joins as soon as
it gets in the car, with Bonjour service discovery so the iOS app finds
the gateway automatically.

## What this installs

| Layer | What | Where |
|---|---|---|
| AP radio | `hostapd` broadcasting SSID `KiSTI` (WPA2-PSK, 2.4 GHz ch. 6) | `/etc/hostapd/hostapd.conf` |
| DHCP + local DNS | `dnsmasq` on the AP interface only, subnet `192.168.42.0/24` | `/etc/dnsmasq.d/kisti.conf` |
| Bonjour | `_kisti._tcp` advertisement on port 8080 | `/etc/avahi/services/kisti.service` |
| HTTP port | `iptables` redirect of inbound :80 → :8080 (AP iface only) | `kisti-ap-up.sh` |
| Captive portal + API | Python stdlib HTTP server on :8080 | `/opt/kisti/captive_portal.py` |

The captive portal exists for one reason: iOS probes `captive.apple.com`
on every WiFi join. If it can't reach Apple's success page, iOS marks the
network as "no internet" and refuses to use it for app traffic. We
DNS-rewrite `captive.apple.com` to the Jetson and serve back Apple's
exact success body — iOS treats the network as fully open. This works
identically whether the Jetson has an upstream uplink or not, so the
behaviour stays consistent when cellular / pit WiFi is added later.

## Install

On the Jetson:

```bash
cd ~/repos/kisti
sudo bash scripts/jetson/install-ap.sh
# enter passphrase when prompted (min 8 chars)

sudo systemctl start kisti-ap-network kisti-captive-portal \
                     hostapd dnsmasq avahi-daemon
```

The installer is idempotent — re-run to rotate the passphrase. Pre-existing
`/etc/hostapd/hostapd.conf` and `/etc/default/hostapd` are saved to
`*.kisti-bak` before overwrite.

## Verify (from the Jetson)

```bash
# Radio is in AP mode
iw dev wlP1p1s0 info | grep type     # should say: type AP

# Services are up
systemctl is-active hostapd dnsmasq kisti-captive-portal avahi-daemon

# Gateway responds locally
curl http://192.168.42.1:8080/v1/health
# {"ok": true, "service": "kisti", "version": 1}

# Captive-portal probe behaves like Apple's
curl -sH 'Host: captive.apple.com' http://192.168.42.1:8080/
# <HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>
```

## Verify (from the iPhone)

1. Settings → Wi-Fi → join **KiSTI** with the passphrase you set.
2. iOS should NOT show "No Internet Connection" — if it does, the
   captive-portal responder is unreachable. Check
   `journalctl -u kisti-captive-portal -f` while reconnecting.
3. Safari → `http://kisti.local:8080/v1/health` should return the
   JSON above. If `kisti.local` doesn't resolve, Bonjour discovery
   is broken — check `avahi-daemon` status.
4. From the eventual iOS app, the Bonjour browser query for
   `_kisti._tcp` resolves to the same host/port.

## Constraints (step 1 only — addressed in later steps)

- **The AP interface is exclusive to the AP role.** While `hostapd` owns
  `wlP1p1s0`, the Jetson can't simultaneously use it as a WiFi client.
  Manage the Jetson over Ethernet for now. Step 3 adds the cellular
  modem and pit-WiFi failover via a separate uplink path.
- **No upstream internet routing yet.** Clients on the AP can reach the
  Jetson (and via the iOS app, can reach the cellular internet through
  the phone's own radio) but the Jetson does not forward traffic to an
  uplink. That's step 3.
- **No `/v1/query` handler yet.** The endpoint returns 501. Step 2 wires
  it into `voice_manager._answer_from_sensors` and `_answer_from_timing`
  so the iOS app can ask sensor / timing questions and get sub-100 ms
  deterministic answers without involving the cloud.

## Revert

```bash
sudo bash scripts/jetson/uninstall-ap.sh
```

Restores backed-up `hostapd.conf` / `default/hostapd`, removes the AP
configs, returns the wireless interface to NetworkManager on next boot.

## Tests

```bash
python3 -m pytest tests/test_captive_portal.py -v
```

Tests cover the probe-detection predicate and full HTTP round-trips against
a live `ThreadingHTTPServer` instance bound to an ephemeral port.
