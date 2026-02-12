#!/bin/bash
# Setup David as a systemd service on VPS
# Run as root on the VPS: bash /opt/david-flip/deploy/setup-systemd.sh

set -e

echo "=== Setting up David as systemd service ==="

# Copy service file
cp /opt/david-flip/deploy/david.service /etc/systemd/system/david.service

# Reload systemd
systemctl daemon-reload

# Enable on boot
systemctl enable david.service

# Start (or restart if already running)
systemctl restart david.service

echo ""
echo "=== David is now a systemd service ==="
echo ""
echo "Useful commands:"
echo "  systemctl status david        # Check status"
echo "  journalctl -u david -f        # Follow logs"
echo "  systemctl restart david       # Restart"
echo "  systemctl stop david          # Stop"
echo "  tail -f /opt/david-flip/data/david.log  # App logs"
echo ""
echo "David will auto-restart on crash (after 10s delay)."
echo "Health check: curl http://localhost:5000/api/health"
