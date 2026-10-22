#!/usr/bin/env python3
"""Original configured Chat actor metadata, native IPC and Linux FD checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]


def main():
    environment=dict(os.environ)
    prefix=environment.get('OVERTE_QT5_HOST_ROOT')
    if prefix:
        prefix=Path(prefix).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),
            PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    commands=[
        [sys.executable,'-Werror::ResourceWarning','-m','unittest',
            'self_tests.test_chat_configured_source','self_tests.test_chat_owned_peer',
            'self_tests.test_chat_input_lifetime_source','self_tests.test_chat_peer_input_close','-v'],
        [sys.executable,str(ROOT/'tests/device/contracts/chat/test_chat_actor_source_native.py')],
        [sys.executable,str(ROOT/'tests/device/contracts/chat/test_chat_actor_pending_native.py')],
        [sys.executable,str(ROOT/'tests/device/contracts/chat/test_chat_actor_input_lifetime_native.py')]]
    for command in commands:
        result=subprocess.run(command,cwd=ROOT/'tests/device',env=environment,check=False)
        if result.returncode:return result.returncode
    return 0


if __name__=='__main__':raise SystemExit(main())
