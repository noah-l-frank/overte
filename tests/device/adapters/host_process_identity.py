"""Actual local Linux host PID/start/boot identity; never target identity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path


def host_identity():
    fields=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    return str(os.getpid())+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
