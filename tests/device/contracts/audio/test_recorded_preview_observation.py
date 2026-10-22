#!/usr/bin/env python3
"""Compile the actual E2E observer with Qt Core and an explicit format seam.

This excludes AudioClient, Qt Multimedia, real audio, Android and OpenXR. The
shim supplies only the missing QAudioFormat value boundary; no PCM is generated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[4]
module = 'Qt6Core'
subprocess.run(['pkg-config', '--exists', module], check=True)
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', module], text=True))
with tempfile.TemporaryDirectory(prefix='recorded-preview-observer-') as directory:
    path = Path(directory)
    (path / 'QAudioFormat').write_text('''#pragma once
class QAudioFormat {
public:
 enum SampleType { SignedInt, Float }; enum Endian { LittleEndian, BigEndian };
 int sampleSize() const { return 16; } SampleType sampleType() const { return SignedInt; }
 Endian byteOrder() const { return LittleEndian; }
 int channelCount() const { return 1; } int sampleRate() const { return 8000; }
};
''')
    (path / 'test.cpp').write_text('''#include <QCoreApplication>
#include <QDateTime>
#include <cassert>
#include "libraries/audio-client/src/RecordedPreviewObservation.h"
int main(int argc, char** argv) {
 QCoreApplication app(argc, argv);
 overte::e2e::RecordedPreviewObservation observer;
 const auto originalStart = QDateTime::currentMSecsSinceEpoch() - 23;
 assert(observer.begin(QAudioFormat{}, originalStart) == 1);
 const QByteArray input("\\x10\\x20\\x30\\x40", 4), sink("\\x50\\x60", 2);
 observer.input(input.constData(), input.size()); observer.sink(sink.constData(), sink.size());
 const QVariantMap event{{"phase", "capturing"}, {"eventSequence", 1}, {"publishedEpochMs", originalStart + 5}};
 observer.event(event);
 const auto original = observer.snapshot();
 assert(original["startedEpochMs"].toLongLong() == originalStart);
 assert(original["inputPcm"].toByteArray() == input && original["sinkPcm"].toByteArray() == sink);
 assert(original["events"].toList() == QVariantList{event});
 assert(observer.snapshot() == original); // A read cannot retime the original.
 observer.clear(); assert(observer.snapshot().isEmpty()); assert(observer.cycle() == 1);
 assert(observer.begin(QAudioFormat{}, originalStart + 1) == 2);
 assert(observer.snapshot()["startedEpochMs"].toLongLong() == originalStart + 1);
 assert(original["inputPcm"].toByteArray() == input); // Original copy survives native release.
 observer.clear(); assert(observer.begin(QAudioFormat{}, 0) == 3); assert(observer.snapshot().isEmpty());
}
''')
    binary = path / 'test'
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fPIC',
        '-I', str(path), '-I', str(ROOT), str(path / 'test.cpp'), '-o', str(binary), *flags], check=True, timeout=60)
    subprocess.run([str(binary)], check=True, timeout=5)
print('PASS: actual recorded-preview observer with Qt Core/format seam; no product or device qualification')
