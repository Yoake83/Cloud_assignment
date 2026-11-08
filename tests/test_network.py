import ipaddress
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_nacl_passes_sample_packets():
    out = subprocess.run([sys.executable, "tools/nacl_sim.py", "network/nacl.json", "network/packets_sample.jsonl",
                          "--check"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "Correct: 6 / 6" in out


def test_extra_nacl_cases():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import nacl_sim
    rules = nacl_sim.load_rules(os.path.join(ROOT, "network", "nacl.json"))

    def d(direction, proto, port, addr):
        return nacl_sim.decide(rules, {"direction": direction, "protocol": proto, "port": port, "address": addr})[0]

    assert d("inbound", "tcp", 80, "198.51.100.200") == "deny"      # abusive range beats the web allow
    assert d("inbound", "tcp", 80, "203.0.113.5") == "allow"
    assert d("inbound", "tcp", 22, "10.20.5.140") == "allow"        # management subnet
    assert d("inbound", "tcp", 22, "10.20.5.20") == "deny"          # data subnet is not management
    assert d("inbound", "tcp", 40000, "10.20.2.9") == "allow"       # reply from the app subnet
    assert d("inbound", "udp", 443, "203.0.113.5") == "deny"
    assert d("outbound", "tcp", 8000, "10.20.3.7") == "allow"
    assert d("outbound", "tcp", 443, "203.0.113.5") == "deny"


def test_subnet_table_matches_allocation_rules():
    base = int(ipaddress.ip_address("10.20.0.0"))
    expected = {"app": "10.20.0.0/22", "public": "10.20.4.0/24", "data": "10.20.5.0/25", "management": "10.20.5.128/27"}
    for name, hosts in (("app", 1000), ("public", 250), ("data", 100), ("management", 20)):
        prefix = 32
        while 2 ** (32 - prefix) - 2 < hosts:
            prefix -= 1
        net = ipaddress.ip_network((base, prefix))
        assert str(net) == expected[name]
        base = int(net.broadcast_address) + 1
    assert json.load(open(os.path.join(ROOT, "network", "nacl.json")))
