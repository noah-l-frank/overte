# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile the real shared inline document contract and exercise Qt/QML values."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


class InlineHtmlDocumentContract(unittest.TestCase):
    def test_actual_document_bytes_and_native_owner_lifetime(self):
        major = os.environ.get("OVERTE_INLINE_QT_MAJOR", "6")
        environment = os.environ.copy()
        libraries = []
        if major == "5":
            prefix = Path(os.environ.get("OVERTE_QT5_ROOT", str(Path.home() / ".local/overte-qt5/root")))
            if (prefix / "usr/lib64/pkgconfig/Qt5Core.pc").is_file():
                environment.update(PKG_CONFIG_PATH=str(prefix / "usr/lib64/pkgconfig"),
                    PKG_CONFIG_SYSROOT_DIR=str(prefix), LD_LIBRARY_PATH=str(prefix / "usr/lib64"),
                    QT_PLUGIN_PATH=str(prefix / "usr/lib64/qt5/plugins"),
                    QML2_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"))
                libraries = ["-L" + str(prefix / "usr/lib64")]
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs",
            "Qt" + major + "Core", "Qt" + major + "Qml"], env=environment, text=True))
        with tempfile.TemporaryDirectory(prefix="overte-inline-document-") as temporary:
            executable = Path(temporary) / "inline-document"
            subprocess.run(["c++", "-std=c++17", "-fPIC", "-UNDEBUG", "-Wall", "-Wextra", "-Werror", "-pthread",
                str(Path(__file__).with_name("inline-html-document-test.cpp")),
                "-I" + str(ROOT / "libraries/shared/src"), "-o", str(executable), *libraries, *flags],
                env=environment, check=True, timeout=60)
            subprocess.run([str(executable)], env=environment, check=True, timeout=20)


if __name__ == "__main__":
    unittest.main()
