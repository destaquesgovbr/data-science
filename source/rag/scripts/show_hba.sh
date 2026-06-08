#!/bin/bash
#
# Show pg_hba.conf (first 30 lines)
#

echo "Current pg_hba.conf (first 30 active lines):"
echo "=============================================="
sudo grep -v "^#" /etc/postgresql/16/main/pg_hba.conf | grep -v "^$" | head -30 | nl
echo
echo "PostgreSQL log (last 20 lines):"
echo "=============================================="
sudo tail -20 /var/log/postgresql/postgresql-16-main.log
