#!/usr/bin/env python3
"""Original normal Erase/reopening and exact profile restoration ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent/'device')]
prefix=os.environ.get('OVERTE_QT5_HOST_ROOT')
if prefix:
    prefix=Path(prefix).resolve(strict=True)
    os.environ.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),OVERTE_CHAT_MOC=str(prefix/'usr/lib64/qt5/bin/moc'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(['self_tests.test_chat_erase_restore','self_tests.test_chat_profile_owner',
        'self_tests.test_chat_profile_current','self_tests.test_chat_profile_native_probe','test_chat_profile_current'])
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
    raise SystemExit(subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/chat/test_chat_profile_current_native.py')],check=False).returncode)
