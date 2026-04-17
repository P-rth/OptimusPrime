Project Name: Smart Home Devices Governance System (hereafter referred to as Inline Sentinel)

Overview:
Inline Sentinel is a lightweight, network-level IoT security system designed to monitor, learn, and enforce device-specific behavior policies without relying on device manufacturers. It operates as a local gateway within a LAN, intercepting DNS and metadata-level traffic to implement a zero-trust, behavior-driven security model for IoT environments.

Core Philosophy:
Do not trust IoT devices. Instead, observe their normal behavior, define constraints, and enforce them at the network level. Avoid deep packet inspection and preserve user privacy by operating only on metadata (DNS queries, traffic frequency, device identity signals).

Deployment Model:

* Runs on a local device (e.g., Raspberry Pi or lightweight server)
* Connected to router via LAN (same subnet)
* Operates using logical interception (DNS + DHCP + NAT), not physical inline routing
* All IoT devices remain connected to router (WiFi/Ethernet)

High-Level Architecture:

1. IoT Devices → connect to router
2. Router → assigns DNS/DHCP controlled by Inline Sentinel
3. Inline Sentinel → intercepts DNS + monitors metadata
4. Processing Pipeline:

   * Identity Discovery
   * Behaviour Learning
   * Policy Generation
   * Enforcement
   * Anomaly Detection
   * Human-in-the-Loop Validation

End-to-End Flow:
Device → DNS Interception → Identification → Behaviour Logging → Policy Engine → Enforcement → Anomaly Detection → User Feedback Loop

---

Phase 1: Device Identity Discovery

Goal:
Accurately identify device manufacturer and type to build a device persona.

Inputs:

* MAC address
* DHCP fingerprint (Option 55)
* mDNS / SSDP broadcasts

Tech Stack:

* MAC OUI lookup (API or local database)
* dnsmasq (DHCP logs)
* Scapy (packet inspection)
* zeroconf / SSDP parsing

Output:
Device Persona:
{
device_id,
manufacturer,
inferred_type,
network_signature
}

---

Phase 2: DNS Enforcement (“God Mode”)

Goal:
Ensure all DNS traffic is routed through Inline Sentinel.

Mechanism:

* DHCP assigns local DNS (CoreDNS)
* iptables redirects all outbound DNS (port 53) to local resolver

Tech Stack:

* CoreDNS (DNS server + logging)
* iptables (NAT redirection)
* dnsmasq (DHCP server)

Key Rule:
iptables -t nat -A PREROUTING -p udp --dport 53 -j REDIRECT

Result:
No device can bypass DNS control, even with hardcoded resolvers.

---

Phase 3: Behaviour Learning (Baseline Generation)

Goal:
Capture normal device behavior under benign conditions.

Captured Data:

* Domain queries
* Request frequency
* Temporal patterns

Storage:

* SQLite (lightweight)
* Aggregated logs (not raw packets)

Output:
Behaviour Profile:
{
device_id,
allowed_domains[],
avg_requests_per_min,
active_time_windows
}

Notes:

* No deep packet inspection
* Metadata only
* Learning phase can be time-bound (e.g., first 24 hours)

---

Phase 4: Policy Engine (Context-Aware Governance)

Goal:
Convert behavior profiles into enforceable rules.

Policy Structure:
{
device_id,
allowed_domains[],
rate_limits,
anomaly_thresholds
}

Implementation:

* Python-based rule engine
* JSON or SQLite-backed policy store

Principle:
Each device is restricted to its known behavior (“least privilege networking”).

---

Phase 5: Enforcement Layer

Goal:
Actively block or allow traffic based on policies.

Mechanisms:

1. DNS Sinkholing

   * Unknown domains → redirected to null/fake IP
2. Firewall Enforcement

   * iptables rules for blocking/bypass prevention
3. Forced DNS Routing

   * All DNS requests pass through CoreDNS

Tech Stack:

* CoreDNS (custom rules/plugins)
* iptables (filter + NAT)

Result:
Unauthorized communication is blocked at resolution stage.

---

Phase 6: Anomaly Detection

Goal:
Detect deviations from baseline behavior.

Triggers:

* New/unseen domains
* Unusual frequency spikes
* Unexpected traffic patterns

Approach:

* Rule-based comparison (no heavy ML required)
* Threshold-based anomaly detection

---

Phase 7: Human-in-the-Loop (HITL) Validation

Goal:
Reduce false positives and improve usability.

Flow:

1. Suspicious domain detected
2. Temporarily blocked via sinkhole
3. User notified with explanation
4. User tests device functionality
5. Decision:

   * If device unaffected → keep blocked
   * If functionality breaks → whitelist domain

Output:
Adaptive policy refinement

---

Data Management Strategy:

* Store only metadata (no payloads)
* Use aggregation (domain + count instead of raw logs)
* Log rotation:

  * Detailed logs: 7–14 days
  * Older logs: summarized or deleted
* Estimated storage:

  * ~1–2 MB/day for 10 devices
  * ~30–60 MB/month

---

Performance Considerations:

* DNS interception adds ~1–5 ms latency
* iptables operates at kernel level (negligible overhead)
* No DPI ensures low CPU usage
* Suitable for Raspberry Pi (10–20 devices)

---

Privacy & Compliance:

* No payload inspection
* Local processing only (no cloud dependency)
* Explicit user consent required
* Aligns with data minimization principles (e.g., DPDP Act)

---

Key Differentiators / USP:

1. Behaviour-Based Security (not static rules)
2. Network-Level Enforcement (not device-dependent)
3. DNS-Centric Control (lightweight, scalable)
4. Human-in-the-Loop Decision System
5. Zero-Trust Model for IoT
6. Fully Local, Privacy-Preserving Design

---

Limitations:

* Initial learning phase required
* Device diversity may cause edge cases
* Scaling to enterprise requires distributed architecture
* Cannot inspect encrypted payload threats (by design)

---

Future Extensions:

* Community-driven MUD/profile sharing
* Edge-cloud hybrid policy sync
* Lightweight ML for anomaly scoring
* Visualization dashboard

---

Summary:

Inline Sentinel is a practical, deployable IoT security layer that combines DNS enforcement, behavioural learning, and user-guided decision making to secure untrusted devices without relying on manufacturers or invasive inspection techniques.
