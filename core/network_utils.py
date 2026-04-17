import logging


def iptables_rule_exists(run_cmd, table: str, chain: str, args: list[str]) -> bool:
    """Return True if the iptables rule exists (iptables -C)."""
    check_cmd = ["sudo", "iptables", "-t", table, "-C", chain] + args
    res = run_cmd(check_cmd)
    return res.returncode == 0


def iptables_add_rule_if_missing(run_cmd, table: str, chain: str, args: list[str]) -> bool:
    """Ensure rule exists; returns True if rule was added, False if already present."""
    if iptables_rule_exists(run_cmd, table, chain, args):
        logging.debug("iptables rule already exists: -t %s %s %s", table, chain, " ".join(args))
        return False
    add_cmd = ["sudo", "iptables", "-t", table, "-A", chain] + args
    run_cmd(add_cmd)
    return True


def iptables_delete_rule(run_cmd, table: str, chain: str, args: list[str]) -> bool:
    """Delete rule; returns True if deletion succeeded (best effort)."""
    del_cmd = ["sudo", "iptables", "-t", table, "-D", chain] + args
    res = run_cmd(del_cmd)
    return res.returncode == 0
