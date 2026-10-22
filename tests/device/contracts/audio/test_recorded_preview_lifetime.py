#!/usr/bin/env python3
"""Whole original AudioClient bodies with real Qt timers and explicit audio seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
moc=None
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    library_paths=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
if moc is None:
    tools=subprocess.check_output(['pkg-config','--variable='+('libexecdir' if major=='6' else 'host_bins'),'Qt'+major+'Core'],text=True,env=environment).strip()
    moc=Path(tools)/'moc'
source=(ROOT/'libraries/audio-client/src/AudioClient.cpp').read_text();header=(ROOT/'libraries/audio-client/src/AudioClient.h').read_text()
def methods(text,owner,names):
    result=[]
    for name in names:
        match=re.search(r'^(?:void|bool|QVariantMap) '+owner+'::'+name+r'\([^\n]*\)(?: const)? \{.*?^\}',text,re.MULTILINE|re.DOTALL)
        assert match is not None,name;result.append(match.group())
    return '\n\n'.join(result)
state=header[header.index('    PhoneVoiceTestBuffer _recordedVoiceTest;'):header.index('    AudioRingBuffer _inputRingBuffer')]
actual=methods(source,'AudioClient',('recordedVoiceTestInputAvailable','publishRecordedVoiceTestStatus','finishRecordedVoiceTest',
    'cancelRecordedVoiceTest','setLocalEcho','setAudioPaused','startRecordedVoiceTest','handleLocalEchoAndReverb','featureRecordedVoiceLifetime','releaseFeatureRecordedVoiceEvidence'))
scripting=methods((ROOT/'libraries/audio/src/AudioScriptingInterface.cpp').read_text(),'AudioScriptingInterface',
    ('setLocalAudioInterface','startRecordedVoiceTest','cancelRecordedVoiceTest','getRecordedVoiceTestStatus','updateRecordedVoiceTestStatus'))
template=Path(__file__).with_name('recorded-voice-native-fixture.cpp').read_text()
fixture=template.replace('@STATE@',state).replace('@METHODS@',actual).replace('@SCRIPTING@',scripting)
fixture=fixture.replace('#include <QCoreApplication>','#include <QCoreApplication>\n#include <QJsonDocument>\n#include <cstdio>\n#include "libraries/audio-client/src/RecordedPreviewDeferred.h"\n#include "libraries/audio-client/src/RecordedPreviewObservation.h"')
fixture=fixture.replace('struct Format {','struct Format : QAudioFormat {')
fixture=fixture.replace('    AudioClient() {','    QVariantMap featureRecordedVoiceLifetime();\n    void releaseFeatureRecordedVoiceEvidence();\n    void setAudioPaused(bool);\n    void negotiateAudioFormat() {} // Explicit format renegotiation seam; no device.\n    AudioClient() {')
helper=fixture.index('static QByteArray pcm(');main=fixture.index('int main(int argc, char** argv) {',helper)
fixture=fixture[:helper]+fixture[main:]
start=fixture.index('int main(int argc, char** argv) {');end=fixture.index('#include "voice.moc"',start)
fixture=fixture[:start]+r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);AudioClient audio;
    if(!QCoreApplication::arguments().contains("--testScript")) {assert(audio.featureRecordedVoiceLifetime().isEmpty());return 0;}
    const auto publish=[&](const QVariantMap& value) {
        const QVariantMap original{{"epoch",QDateTime::currentMSecsSinceEpoch()},{"cycle",static_cast<qulonglong>(audio._e2eRecordedVoiceCycle)},{"source",value}};
        std::puts(QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact).constData());
    };
    const auto initial=audio.featureRecordedVoiceLifetime();assert(!initial.isEmpty());publish(initial);
    assert(initial.value("previewTapStateEmpty").toBool());
    assert(initial.value("deferred").toMap().value("callbacks").toList().isEmpty());
    audio._isMuted=true;audio.startRecordedVoiceTest();assert(audio.status.value("error")=="microphone-muted");
    const auto owned=audio.featureRecordedVoiceLifetime();publish(owned);auto rows=owned.value("deferred").toMap().value("callbacks").toList();assert(rows.size()==1);
    const auto original=rows.first().toMap();assert(original.value("scheduledDelayMs")==30000&&!original.value("retired").toBool());
    assert(original.value("enteredEpochMs").toLongLong()==0&&original.value("receiverAlive").toBool());
    assert(!owned.value("previewTapStateEmpty").toBool());
    audio.releaseFeatureRecordedVoiceEvidence();const auto released=audio.featureRecordedVoiceLifetime();
    assert(released.value("previewTapStateEmpty").toBool());assert(!released.value("deferred").toMap().value("callbacks").toList().first().toMap().value("retired").toBool());
    assert(!released.value("previewTimer").toMap().value("created").toBool());
    // The exact original production singleShot(30000,this,...) runs naturally.
    // PCM release and passing requested time cannot substitute for invocation
    // and destruction of the original captured Qt functor.
    QElapsedTimer elapsed;elapsed.start();QVariantMap ended;
    while(elapsed.elapsed()<33000) {
        pump(50);const auto value=audio.featureRecordedVoiceLifetime();
        ended=value.value("deferred").toMap().value("callbacks").toList().first().toMap();
        if(ended.value("retired").toBool()) {break;}
    }
    assert(ended.value("id")==original.value("id")&&ended.value("registeredEpochMs")==original.value("registeredEpochMs"));
    assert(ended.value("retired").toBool()&&!ended.value("active").toBool());
    assert(ended.value("enteredEpochMs").toLongLong()>=original.value("registeredEpochMs").toLongLong()+28500);
    assert(ended.value("completedEpochMs").toLongLong()>=ended.value("enteredEpochMs").toLongLong());
    assert(ended.value("retiredEpochMs").toLongLong()>=ended.value("completedEpochMs").toLongLong());
    assert(audio.featureRecordedVoiceLifetime().value("previewTapStateEmpty").toBool());publish(audio.featureRecordedVoiceLifetime());
    // A canceled Qt context releases its actual closure lease, too; the dead
    // AudioClient itself would be unavailable to its existing weak reader.
    overte::e2e::RecordedPreviewDeferred tracker;auto receiver=std::make_unique<QObject>();
    auto lease=tracker.registerCallback(receiver.get(),1,1000);assert(lease);std::weak_ptr<overte::e2e::RecordedPreviewDeferred::Lease> weak=lease;
    QTimer::singleShot(1000,receiver.get(),[lease]{});lease.reset();assert(!weak.expired());receiver.reset();assert(tracker.snapshot(nullptr).isEmpty());
    // Receiver death can leave the original Qt single-shot functor retained
    // until its actual queued timer cleanup. Never infer lease death from it.
    QElapsedTimer canceled;canceled.start();while(!weak.expired()&&canceled.elapsed()<1500){pump(20);}
    assert(weak.expired());
    // Original preview polling timer construction/start/stop is also observed
    // without replacing it or deleting an internal Qt timer.
    audio._isMuted=false;audio._androidAudioInputActive=true;audio.startRecordedVoiceTest();
    const auto timer=audio.featureRecordedVoiceLifetime().value("previewTimer").toMap();
    assert(timer.value("created").toBool()&&timer.value("alive").toBool()&&timer.value("active").toBool());
    audio.cancelRecordedVoiceTest();const auto stopped=audio.featureRecordedVoiceLifetime().value("previewTimer").toMap();
    assert(stopped.value("id")==timer.value("id")&&stopped.value("alive").toBool()&&!stopped.value("active").toBool());publish(audio.featureRecordedVoiceLifetime());
    // Entire original pause body publishes its actual cancellation; this is
    // an explicit pause boundary, not an OS HOME or microphone-device proof.
    audio.startRecordedVoiceTest();audio.setAudioPaused(true);
    assert(!audio._recordedVoiceTestActive&&audio.status.value("phase")=="cancelled"&&audio.status.value("error")=="backgrounded");
    publish(audio.featureRecordedVoiceLifetime());audio.setAudioPaused(false);
    // The original 250ms polling functor independently observes actual input
    // availability loss. No native result is supplied by a requested outcome.
    audio.startRecordedVoiceTest();assert(audio._recordedVoiceTestActive);
    audio._androidAudioInputActive=false;audio._audioInput=nullptr;audio._inputDevice=nullptr;
    QElapsedTimer unavailable;unavailable.start();while(audio._recordedVoiceTestActive&&unavailable.elapsed()<1500){pump(20);}
    assert(!audio._recordedVoiceTestActive&&audio.status.value("phase")=="cancelled"&&audio.status.value("error")=="input-or-lifecycle-changed");
    assert(!audio.featureRecordedVoiceLifetime().value("previewTimer").toMap().value("active").toBool());publish(audio.featureRecordedVoiceLifetime());
    const auto originalTimer=audio._recordedVoiceTestTimer;audio._recordedVoiceTestTimer=nullptr;
    assert(audio.featureRecordedVoiceLifetime().isEmpty());audio._recordedVoiceTestTimer=originalTimer;
    qInfo("PASS original AudioClient30s cleanup callback invocation/functor release and actual preview timer; explicit audio seams, no devices");
}
'''+fixture[end:]
with tempfile.TemporaryDirectory(prefix='recorded-preview-lifetime-') as directory:
    private=Path(directory);private.chmod(0o700)
    (private/'QAudioFormat').write_text('''#pragma once
class QAudioFormat {public:enum SampleType {SignedInt};enum Endian {LittleEndian};
int sampleSize()const{return 16;}SampleType sampleType()const{return SignedInt;}Endian byteOrder()const{return LittleEndian;}
int sampleRate()const{return 48000;}int channelCount()const{return 2;}};
''')
    cpp=private/'voice.cpp';cpp.write_text(fixture)
    subprocess.run([str(moc),'-DOVERTE_E2E_FEATURE_TESTS',str(cpp),'-o',str(private/'voice.moc')],check=True,timeout=30,env=environment)
    binary=private/'test'
    subprocess.run(['c++','-std=c++17','-UNDEBUG','-Wall','-Wextra','-Werror','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(ROOT),'-I'+str(private),str(cpp),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    clock_binary=private/'clock-test'
    subprocess.run(['c++','-std=c++17','-UNDEBUG','-Wall','-Wextra','-Werror','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS',
        '-I'+str(ROOT),str(Path(__file__).with_name('recorded-preview-deferred-clock-test.cpp')),'-o',str(clock_binary),*library_paths,*flags],
        check=True,timeout=60,env=environment)
    subprocess.run([str(clock_binary),'--testScript'],check=True,timeout=10,env=environment)
    subprocess.run([str(binary)],check=True,timeout=10,env=environment)
    raw=subprocess.check_output([str(binary),'--testScript'],text=True,timeout=38,env=environment)
    sys.path.insert(0,str(ROOT/'tests/device'))
    from adapters.audio_preview_lifetime import validate,accept
    previous=None
    for line in raw.splitlines():
        packet=json.loads(line);validate(packet['source'],packet['epoch'],packet['cycle']);previous=accept(previous,packet['source'])
    assert previous is not None
