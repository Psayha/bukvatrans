#!/bin/sh
# Add a 2 GiB swapfile on the host. The default VPS comes with no swap;
# under transient memory pressure (npm rebuild, peak transcription load,
# watchtower image pull) the kernel OOM-killer reaps random victims —
# in practice it kept killing api/uvicorn, taking the bot offline.
#
# Run once on the host (NOT inside a container). Idempotent: re-running
# is a no-op.
#
#   sudo sh scripts/enable_swap.sh
#
# Verify with:  free -h  &&  swapon --show
set -eu

SWAPFILE=${SWAPFILE:-/swapfile}
SIZE_GB=${SIZE_GB:-2}

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo sh $0" >&2
    exit 1
fi

if swapon --show | grep -q "^${SWAPFILE} "; then
    echo "${SWAPFILE} is already active:"
    swapon --show
    exit 0
fi

if [ -f "${SWAPFILE}" ]; then
    echo "${SWAPFILE} exists but is not active — activating."
else
    echo "Creating ${SIZE_GB} GiB swapfile at ${SWAPFILE}..."
    # fallocate is fastest but doesn't work on some filesystems (e.g. ext4
    # without extents). Fall back to dd in that case.
    fallocate -l "${SIZE_GB}G" "${SWAPFILE}" 2>/dev/null || \
        dd if=/dev/zero of="${SWAPFILE}" bs=1M count=$((SIZE_GB * 1024)) status=progress
    chmod 600 "${SWAPFILE}"
    mkswap "${SWAPFILE}"
fi

swapon "${SWAPFILE}"

# Persist across reboot.
if ! grep -q "^${SWAPFILE}" /etc/fstab; then
    echo "${SWAPFILE} none swap sw 0 0" >> /etc/fstab
    echo "Added ${SWAPFILE} to /etc/fstab."
fi

# Modest swappiness so the kernel only swaps under genuine pressure.
sysctl -w vm.swappiness=10 >/dev/null
if [ -d /etc/sysctl.d ]; then
    echo "vm.swappiness=10" > /etc/sysctl.d/99-bukvatrans-swap.conf
fi

echo
echo "Done."
free -h
swapon --show
