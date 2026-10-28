#!/bin/sh
# The workers share this container's network, so these rules bind every process in them,
# including ffmpeg and curl_cffi, which the Python check in app/core/netguard.py cannot see.
set -eu

subnet=$(ip -4 route | awk '/scope link/ { print $1; exit }')
gateway=$(ip -4 route | awk '/^default/ { print $3; exit }')
[ -n "$subnet" ] && [ -n "$gateway" ]

for table in iptables ip6tables; do
	$table -F OUTPUT
	$table -A OUTPUT -o lo -j ACCEPT
	$table -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
done

for cidr in $(echo "${EGRESS_DENY_CIDRS:-}" | tr ',' ' '); do
	case $cidr in
	*:*) ip6tables -A OUTPUT -d "$cidr" -j REJECT ;;
	*) iptables -A OUTPUT -d "$cidr" -j REJECT ;;
	esac
done

# Redis and cobalt sit on our own network. The gateway is the host itself, with whatever else
# runs there.
iptables -A OUTPUT -d "$gateway" -j REJECT
iptables -A OUTPUT -d "$subnet" -j ACCEPT

for cidr in $(echo "${EGRESS_ALLOW_CIDRS:-}" | tr ',' ' '); do
	case $cidr in
	*:*) ip6tables -A OUTPUT -d "$cidr" -j ACCEPT ;;
	*) iptables -A OUTPUT -d "$cidr" -j ACCEPT ;;
	esac
done

for cidr in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 \
	192.0.0.0/24 192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 \
	224.0.0.0/3; do
	iptables -A OUTPUT -d "$cidr" -j REJECT
done
for cidr in ::/128 ::1/128 ::ffff:0:0/96 64:ff9b:1::/48 100::/64 2001:db8::/32 fc00::/7 \
	fe80::/10 ff00::/8; do
	ip6tables -A OUTPUT -d "$cidr" -j REJECT
done

touch /tmp/ready
exec sleep infinity
