import logging

from .network_utils import iptables_add_rule_if_missing, iptables_delete_rule, iptables_rule_exists


class GodModeDNSRedirect:
    """Implements DNS redirection ("God Mode") rules for iptables.

    This class is designed to be used with an existing NetworkManager-like instance
    that provides:
      - self.config.WIFI_IFACE
      - self.config.GATEWAY_IP
      - self.run_cmd(cmd, ...)

    It stores the exact rules it adds so they can be removed later.
    """

    def __init__(self, network_manager):
        self.nm = network_manager
        self.dns_rules = []

    def apply(self):
        # --- God Mode DNS Redirection (DNS Hijack) ---
        # Redirect *all* client DNS queries (even to hardcoded resolvers like 8.8.8.8)
        # entering on the Wi-Fi interface to our local CoreDNS at GATEWAY_IP:53.
        # The -i WIFI_IFACE match prevents looping the Pi's own system traffic.
        self.dns_rules = [
            (
                "nat",
                "PREROUTING",
                [
                    "-i",
                    self.nm.config.WIFI_IFACE,
                    "-p",
                    "udp",
                    "--dport",
                    "53",
                    "-j",
                    "DNAT",
                    "--to-destination",
                    f"{self.nm.config.GATEWAY_IP}:53",
                ],
            ),
            (
                "nat",
                "PREROUTING",
                [
                    "-i",
                    self.nm.config.WIFI_IFACE,
                    "-p",
                    "tcp",
                    "--dport",
                    "53",
                    "-j",
                    "DNAT",
                    "--to-destination",
                    f"{self.nm.config.GATEWAY_IP}:53",
                ],
            ),
        ]

        for table, chain, args in self.dns_rules:
            if iptables_rule_exists(self.nm.run_cmd, table, chain, args):
                logging.info("DNS Hijack rule already exists")
                continue

            added = iptables_add_rule_if_missing(self.nm.run_cmd, table, chain, args)
            if added:
                logging.info("DNS Hijack Active")
            else:
                logging.info("DNS Hijack rule already exists")

    def remove(self):
        for table, chain, args in self.dns_rules:
            if iptables_delete_rule(self.nm.run_cmd, table, chain, args):
                logging.info("DNS Hijack rule removed")
            else:
                logging.debug(
                    "DNS Hijack rule not present or failed to remove: %s",
                    " ".join(["-t", table, "-D", chain] + args),
                )
