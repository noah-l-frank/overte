#!/usr/bin/env python3
"""Execute the iOS inline binding against real Qt and a proven owning API.

Before normal parent propagation, the coordinator-approved Main contract may
only be a read-only SHA-bound API input. This never copies it into the leaf or
establishes native SDK/source closure. Missing inputs fail rather than skip.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PINNED_MAIN_API = "4a568e57ef28daa8bac42f49e7c1e39917598503"


def body(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def owning_api():
    shared = ROOT / "libraries/shared/src"
    if (shared / "InlineHtmlDocument.h").is_file():
        return shared, "in-tree owning parent"
    external = os.environ.get("OVERTE_IOS_INLINE_API_ROOT")
    if not external:
        raise SystemExit("InlineHtmlDocument must propagate from its owning parent. For explicitly approved host-only preparation, set OVERTE_IOS_INLINE_API_ROOT to the read-only Main contract checkout at " + PINNED_MAIN_API)
    checkout = Path(external).resolve()
    shared = checkout / "libraries/shared/src"
    for relative in ("libraries/shared/src/InlineHtmlDocument.h", "libraries/shared/src/EmbeddedWebPolicy.h",
                     "interface/resources/qml/controls/EmbeddedWebView.qml"):
        original = subprocess.check_output(["git", "-C", str(checkout), "show", PINNED_MAIN_API + ":" + relative])
        if (checkout / relative).read_bytes() != original:
            raise SystemExit("Read-only owning Main API differs from the explicitly pinned contract: " + relative)
    return shared, "read-only Main API " + PINNED_MAIN_API + "; NOT propagated/source-closed"


shared, api_binding = owning_api()
major = os.environ.get("OVERTE_IOS_INLINE_QT_MAJOR", "6")
if major not in ("5", "6"):
    raise SystemExit("OVERTE_IOS_INLINE_QT_MAJOR must be 5 or 6")
modules = ["Qt" + major + module for module in ("Core", "Gui", "Qml", "Quick")]
flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", *modules], text=True))
variable = "host_bins" if major == "5" else "libexecdir"
moc = Path(subprocess.check_output(["pkg-config", "--variable=" + variable, "Qt" + major + "Core"], text=True).strip()) / "moc"
if not moc.is_file() and os.environ.get("PKG_CONFIG_SYSROOT_DIR"):
    moc = Path(os.environ["PKG_CONFIG_SYSROOT_DIR"]) / str(moc).lstrip("/")
source = (ROOT / "ios/web/IOSWebView.mm").read_text()
header = (ROOT / "ios/web/IOSWebView.h").read_text()
properties = "\n".join(line for line in header.splitlines()
    if re.search(r"Q_PROPERTY\(\w+ (url|scriptUrl|inlineDocument) ", line))
if len(properties.splitlines()) != 3:
    raise SystemExit("The actual native property declarations must be tested")
signatures = ("QString IOSWebView::url(", "void IOSWebView::setUrl(",
              "QString IOSWebView::scriptUrl(", "void IOSWebView::setScriptUrl(",
              "QVariant IOSWebView::inlineDocument(", "void IOSWebView::setInlineDocument(")
with tempfile.TemporaryDirectory(prefix="ios-inline-document-") as temporary:
    stage = Path(temporary)
    (stage / "production-properties-methods.inc").write_text("\n".join(body(source, signature) for signature in signatures))
    # moc does not scan Q_PROPERTY declarations hidden in a normal #include.
    # Expand only the actual production declarations into the fixture translation
    # unit so both moc and C++ see the same native Qt property metadata.
    driver = stage / "inline-test.cpp"
    driver.write_text(Path(__file__).with_suffix(".cpp").read_text().replace(
        '#include "production-properties.inc"', properties))
    subprocess.run([str(moc), str(driver), "-o", str(stage / "inline-test.moc")], check=True, timeout=20)
    binary = stage / "inline-document"
    subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC",
        "-I" + str(shared), "-I" + str(stage), "-I" + str(ROOT / "ios/tests"), str(driver), "-o", str(binary), *flags], check=True, timeout=90)
    subprocess.run([str(binary), str(shared.parents[2]), str(ROOT)], check=True, timeout=30, env=os.environ | {
        "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"})
print("API binding: " + api_binding)
print("Apple SDK, actual WK rules/origin/network/history and video: NOT_PERFORMED")
