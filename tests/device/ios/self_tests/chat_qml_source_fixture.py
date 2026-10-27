"""Explicit uncompiled Qt/native producer model; real reviewed QML source pin."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from ios.adapters import chat_qml_sources as source

ROOT = Path(__file__).resolve().parents[4]
URL = 'qrc:/scripts/' + source.QML
RUN = 'a' * 32
EPOCH = 1700000000000


def packet(epoch=EPOCH):
    raw = (ROOT / 'scripts' / source.QML).read_bytes().decode('utf-8').encode('utf-16le')
    compiler = dict(qtOverteQmlCompilerInputVersion=1, instance='b' * 32, sequence=1, processId=42,
        qtVersion='6.11.1', encoding='utf16-le-code-units', codeUnits=len(raw) // 2,
        sha256=hashlib.sha256(raw).hexdigest(), requestedUrl=URL, resolvedUrl=URL,
        sourceBeforeEpochMs=epoch + 100, sourceAfterEpochMs=epoch + 102, compiledEpochMs=epoch + 104,
        compilerUnitBytes=2048, compilerUnitSha256='c' * 64, unitBytes=2048, unitSha256='c' * 64, unitGeneration=0)
    loaded = dict(iosLoadedQmlSourceVersion=1, instance='d' * 32, loadSequence=1, loadId='e' * 32,
        objectId='f' * 32, creationContextId='1' * 32, objectContextId='2' * 32, processId=42,
        clockDomain='native-main-qml-load', loadBefore=dict(epochMs=epoch + 90, monotonicMs=90),
        loadCompleted=dict(epochMs=epoch + 110, monotonicMs=110), requestedUrl=URL,
        selectedUrl=URL, componentUrl=URL, creationContextUrl='qrc:/qml/hifi/tablet/', objectContextUrl=URL,
        compilerInput=compiler)
    return dict(iosChatQmlSourcesVersion=1, requestId='ios-' + '3' * 32, runId=RUN, instance='4' * 32,
        sequence=1, processId=42, clockDomain='native-main-chat-qml-sources',
        clockBefore=dict(epochMs=epoch + 1000, monotonicMs=1000),
        clockAfter=dict(epochMs=epoch + 1001, monotonicMs=1001), pageControlSourceSha256='5' * 64, source=loaded)


def advance(value):
    result = deepcopy(value)
    result.update(requestId='ios-' + '6' * 32, sequence=value['sequence'] + 1)
    for name in ('clockBefore', 'clockAfter'):
        result[name]['epochMs'] += 10; result[name]['monotonicMs'] += 10
    return result


class Boundary:
    def __init__(self, epoch=20000):
        self.epoch, self.time, self.sequence = epoch, 1000, 0
        self.value, self.raw, self.queries, self.mutate = packet(epoch), '', [], None

    def send(self, query):
        self.queries.append(deepcopy(query)); self.sequence += 1
        value = deepcopy(self.value); self.time += 1
        value.update(requestId=query['commandId'], runId=query['runId'], sequence=self.sequence,
            clockBefore=dict(epochMs=self.epoch + self.time, monotonicMs=self.time))
        self.time += 1
        value['clockAfter'] = dict(epochMs=self.epoch + self.time, monotonicMs=self.time)
        if self.mutate:
            self.mutate(value)
        self.raw = json.dumps(value)
