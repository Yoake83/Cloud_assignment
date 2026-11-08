# Subnet allocation for 10.20.0.0/16

Rule used: usable hosts = 2^(32 - prefix) - 2. For each requirement take the smallest prefix whose usable hosts
cover it. Allocate from the largest requirement to the smallest, each subnet right after the previous one,
starting at 10.20.0.0.

## Working

| Subnet | Hosts needed | Host bits h with 2^h - 2 >= hosts | Prefix = 32 - h |
|---|---|---|---|
| app | 1,000 | h = 10 (2^10 - 2 = 1,022; h = 9 gives only 510) | /22 |
| public | 250 | h = 8 (2^8 - 2 = 254; h = 7 gives only 126) | /24 |
| data | 100 | h = 7 (2^7 - 2 = 126; h = 6 gives only 62) | /25 |
| management | 20 | h = 5 (2^5 - 2 = 30; h = 4 gives only 14) | /27 |

Sizes in addresses: /22 = 1,024, /24 = 256, /25 = 128, /27 = 32.
- app starts at 10.20.0.0 and covers 1,024 addresses: 10.20.0.0 - 10.20.3.255.
- public starts at 10.20.4.0 (next address) and covers 256: 10.20.4.0 - 10.20.4.255.
- data starts at 10.20.5.0 and covers 128: 10.20.5.0 - 10.20.5.127.
- management starts at 10.20.5.128 and covers 32: 10.20.5.128 - 10.20.5.159.

## Result

| Subnet | Network address | Prefix | Usable host range | Broadcast address | Usable hosts |
|---|---|---|---|---|---|
| app | 10.20.0.0 | /22 | 10.20.0.1 - 10.20.3.254 | 10.20.3.255 | 1,022 |
| public | 10.20.4.0 | /24 | 10.20.4.1 - 10.20.4.254 | 10.20.4.255 | 254 |
| data | 10.20.5.0 | /25 | 10.20.5.1 - 10.20.5.126 | 10.20.5.127 | 126 |
| management | 10.20.5.128 | /27 | 10.20.5.129 - 10.20.5.158 | 10.20.5.159 | 30 |

## NACL for the public subnet (network/nacl.json)

Inbound (rules are checked from the lowest number upward, first match wins, default deny):

| Rule | Protocol / ports | Source | Action | Why |
|---|---|---|---|---|
| 100 | all | 198.51.100.0/24 | deny | abusive range, must come before the web-port allows |
| 200 | tcp 80 | 0.0.0.0/0 | allow | HTTP |
| 210 | tcp 443 | 0.0.0.0/0 | allow | HTTPS |
| 220 | tcp 22 | 10.20.5.128/27 (management) | allow | SSH only from management |
| 230 | tcp 1024-65535 | 10.20.0.0/22 (app) | allow | replies coming back from the app subnet (the load balancer's ephemeral ports) |

Outbound:

| Rule | Protocol / ports | Destination | Action | Why |
|---|---|---|---|---|
| 100 | tcp 8000 | 10.20.0.0/22 (app) | allow | load balancer to the service |
| 200 | tcp 1024-65535 | 0.0.0.0/0 | allow | replies going back to clients (ephemeral ports) |

## Why replies need their own rule, and why rule order matters

A NACL is stateless: it does not remember that an inbound request was allowed, so the reply is a brand-new
packet that is checked against the outbound rules on its own. A client connects from a random ephemeral port
(1024-65535) to port 443; the reply goes back to that ephemeral port, so the outbound side needs an explicit
allow for 1024-65535, and the same applies to the app subnet's replies on the inbound side.

Rules are evaluated from the lowest rule number and the first match decides. The deny for 198.51.100.0/24 is
rule 100, lower than the allows for ports 80 and 443 (200, 210). If it had a higher number, a packet from that
range to port 443 would match the allow first and be let in, and the deny would never be reached.
