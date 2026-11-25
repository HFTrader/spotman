#!/bin/bash
# First-boot setup for profiles/zen5-c8a-metal.yaml (cloud-init user data, runs as root, once).
# Isolation is not done here: it needs ~/git/tests/cpu-isolation from the laptop and a reboot,
# so it runs as the profile's setup_steps (spotman create / spotman setup).

# Backstop: power off (a one-time spot instance then terminates) 6 h after first boot.
# The profile sets shutdown_behavior: terminate. The cron check survives reboots. Extend with:
#   ssh HOST 'echo $(( $(date +%s) + 3*3600 )) | sudo tee /etc/spotman-deadline'
echo $(( $(date +%s) + 6*3600 )) > /etc/spotman-deadline
cat > /etc/cron.d/spotman-deadline <<'EOF'
*/5 * * * * root [ $(date +\%s) -gt $(cat /etc/spotman-deadline) ] && /sbin/poweroff
EOF

# irqbalance off: the isolation kit writes a 64-bit IRQBALANCE_BANNED_CPUS mask, which on this
# 96-CPU box leaves cores 64-95 open, and irqbalance spread IRQs onto isolated cores (2026-11-25).
# Without it the kit's boot-time tune keeps every movable IRQ on the housekeeping cores.
systemctl disable --now irqbalance || true

# Hardware counters from user space (the benchmark harnesses use perf_event_open).
echo 'kernel.perf_event_paranoid = 1' > /etc/sysctl.d/90-perf.conf
sysctl -q -p /etc/sysctl.d/90-perf.conf

# Compilers. g++-14 matches the other benchmark boxes; Ubuntu 26.04's default g++ is 15.
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update > /var/log/zen5-setup-apt.log 2>&1
apt-get -qq install -y build-essential g++-14 >> /var/log/zen5-setup-apt.log 2>&1

touch /var/lib/zen5-setup-done
