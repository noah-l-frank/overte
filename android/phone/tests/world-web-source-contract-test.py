#!/usr/bin/env python3
"""Compile the actual E2E provider with QtCore and synthetic item/JNI boundaries.

This checks native provider/grammar logic only. It does not compile the Android
NativeWebViewItem translation unit or prove Android pointer/IME/browser behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir',required=True,type=Path)
args=parser.parse_args();build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=False)
source=r'''
#define OVERTE_E2E_FEATURE_TESTS
#define ANDROID_APP_PHONE_INTERFACE
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMutex>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <jni.h>
#include <cassert>
#include "tests/device/native/PhoneWorldWebBridge.h"
#include "tests/device/native/PhoneWebRuntimeBridge.h"
struct Session {
    QUrl original;quint64 generation() const { return 1; }
    QUrl url() const { return original; }
};
class NativeWebViewItem:public QObject {
public:
    enum Surface { Tablet,WorldEntity };
    Surface _surface{WorldEntity};Session _session;QUrl _document;QMutex _mutex;
    jlong _handle{42};quint64 _page{1},_creationRevision{1},_featureWebFinishedGrant{1},_featureWebFinishedPage{1};
    QUrl _featureWebFinishedDocument;QString _sourceIdentity{"original-item"};
    quint64 _featureWebHTTPGrant{0},_featureWebHTTPPage{0};int _featureWebHTTPStatus{0};bool _inlineProvided{false};
    struct Inline { bool active{false};bool current() const { return active; } } _inlineDocument;
    static QVariantMap featurePhoneWorldWeb(const QVariantMap&);
    static void acceptFeatureWorldWebInput(const QString&,bool);
    void featureWorldWebRecord(const QString&,const QVariant& value={});
    bool allowsEditorDocument(quint64 grant,quint64 page,const QUrl& document) const {
        return grant==1 && page==_page && document==_document;
    }
    QVariantMap featureWebDOMRequest(const QVariantMap& command) {
        QVariantMap packet{{"status","ready"},{"commandId",command.value("commandId")},
            {"source",QVariantMap{{"dom",QVariantMap{{"instance","original-dom"},{"sequence",1},
                {"attempts",QVariantList{}},{"echoes",QVariantList{}}}}}}};
        featureWorldWebRecord("dom",packet);return packet;
    }
};
QMutex registryMutex;QHash<jlong,NativeWebViewItem*> registry;
bool featureEnabled() { return true; }
struct Jni { JNIEnv* env{nullptr};jstring string(const QString&) { return nullptr; } };
bool call(const char*,const char*,jvalue*) { return false; }
QString string(JNIEnv*,jstring) { return {}; }
#include "android/common/web/src/PhoneWorldWebE2E.inc"
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    const QString run(32,'a'),token(32,'b'),ticket(32,'c');
    const QString root="http://127.0.0.1:50001/feature-fixture/v1/runs/"+run+"/";
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'d')},{"action","phone-world-web"},
        {"runId",run},{"fixtureUrl",root},{"ownerToken",token},{"operation","reserve"}};
    assert(overte::e2e::phoneWorldWebCommand(command));
    auto unknown=command;unknown.insert("expectedState",true);assert(!overte::e2e::phoneWorldWebCommand(unknown));
    auto reply=NativeWebViewItem::featurePhoneWorldWeb(command);assert(reply.value("status")=="ready");
    auto wrong=command;wrong.insert("ownerToken",QString(32,'e'));assert(NativeWebViewItem::featurePhoneWorldWeb(wrong).isEmpty());
    NativeWebViewItem item;item._session.original=QUrl(root+"tickets/"+ticket+"/index.html");item._document=item._session.original;
    registry.insert(42,&item);item.featureWorldWebRecord("documents");item.featureWorldWebRecord("documents");
    command.insert("operation","observe");command.insert("commandId",QString(32,'e'));
    reply=NativeWebViewItem::featurePhoneWorldWeb(command);
    assert(reply.value("status")=="ready");assert(reply.value("source").toMap().value("documents").toList().size()==1);
    const QString request="{\"contract\":\"overte-web-parity-v1\",\"action\":\"echo\",\"sequence\":1}";
    item.featureWorldWebRecord("requests",request);
    item.featureWorldWebRecord("replies",QString("{\"contract\":\"overte-web-parity-v1\",\"action\":\"echo\",\"sequence\":1,\"surface\":\"world\"}"));
    command.insert("commandId",QString(32,'f'));reply=NativeWebViewItem::featurePhoneWorldWeb(command);
    assert(reply.value("source").toMap().value("requests").toList().size()==1);
    assert(reply.value("source").toMap().value("replies").toList().size()==1);
    // A new actual document adds a load; repeated completion does not.
    item._page=2;item._document=QUrl(root+"tickets/"+ticket+"/page-b.html");item.featureWorldWebRecord("documents");
    command.insert("commandId",QString(32,'1'));reply=NativeWebViewItem::featurePhoneWorldWeb(command);
    assert(reply.value("source").toMap().value("documents").toList().size()==2);
    // Native retirement cannot forget a still existing original item.
    command.insert("operation","retire");command.insert("commandId",QString(32,'3'));assert(NativeWebViewItem::featurePhoneWorldWeb(command).isEmpty());
    registry.clear();reply=NativeWebViewItem::featurePhoneWorldWeb(command);assert(reply.value("status")=="ready");
    command.insert("operation","observe");command.insert("commandId",QString(32,'2'));reply=NativeWebViewItem::featurePhoneWorldWeb(command);
    auto original=reply.value("source").toMap();assert(original.value("retired")==true);
    assert(original.value("documents").toList().isEmpty() && original.value("current").toMap().isEmpty());
    // The native reservation tombstone cannot be reused as a fresh run.
    command.insert("operation","reserve");assert(NativeWebViewItem::featurePhoneWorldWeb(command).isEmpty());
    // Real command grammar checks a finite, exact current context and controls.
    command.insert("operation","input");command.insert("handle","42");command.insert("creation",1);
    command.insert("grant",1);command.insert("page",2);command.insert("control","bridge");command.insert("text","");
    assert(overte::e2e::phoneWorldWebCommand(command));
    command.insert("page",true);assert(!overte::e2e::phoneWorldWebCommand(command));
    // The separately typed original /parity/ path qualifies video controls only.
    QVariantMap reference{{"schemaVersion",1},{"commandId",QString(32,'6')},{"action","phone-web-reference"},
        {"runId",QString(32,'7')},{"fixtureUrl","http://127.0.0.1:50001/parity/"},{"ownerToken",QString(32,'8')},
        {"operation","reserve"},{"surface","world"}};
    assert(overte::e2e::phoneWorldWebCommand(reference));
    reply=NativeWebViewItem::featurePhoneWorldWeb(reference);assert(reply.value("status")=="ready");
    item._session.original=QUrl("http://127.0.0.1:50001/parity/index.html");item._document=item._session.original;
    item._page=1;item._featureWebFinishedGrant=1;item._featureWebFinishedPage=1;item._featureWebFinishedDocument=item._document;
    registry.insert(42,&item);item.featureWorldWebRecord("documents");
    reference.insert("operation","observe");reference.insert("commandId",QString(32,'9'));
    reply=NativeWebViewItem::featurePhoneWorldWeb(reference);assert(reply.value("status")=="ready");
    assert(reply.value("source").toMap().value("current").toMap().value("nativeView").toMap().value("nativeFinished")==true);
    const auto originalReply=reply;
    assert(NativeWebViewItem::featurePhoneWorldWeb(reference)==originalReply); // Never retime a completed nonce.
    item._featureWebHTTPGrant=1;item._featureWebHTTPPage=1;item._featureWebHTTPStatus=404;
    item._inlineProvided=true;item._inlineDocument.active=true;reference.insert("commandId",QString(32,'c'));
    reply=NativeWebViewItem::featurePhoneWorldWeb(reference);
    const auto errorView=reply.value("source").toMap().value("current").toMap().value("nativeView").toMap();
    assert(errorView.value("httpErrorStatus")==404 && errorView.value("inlineLease")==true);
    reference.insert("operation","input");reference.insert("commandId",QString(32,'a'));reference.insert("handle","42");
    reference.insert("creation",1);reference.insert("grant",1);reference.insert("page",1);reference.insert("control","play");reference.insert("text","");
    assert(overte::e2e::phoneWorldWebCommand(reference));
    reference.insert("control","bridge");assert(!overte::e2e::phoneWorldWebCommand(reference));
    reference.insert("control","play");reference.insert("fixtureUrl",root);assert(!overte::e2e::phoneWorldWebCommand(reference));
    QVariantMap runtime{{"schemaVersion",1},{"commandId",QString(32,'b')},{"action","feature-phone-web-reference-runtime-observe"},
        {"runId",run},{"fixtureUrl","http://127.0.0.1:50001/parity/"}};
    assert(overte::e2e::phoneWebRuntimeCommand(runtime));
    runtime.insert("action","feature-phone-web-runtime-observe");assert(!overte::e2e::phoneWebRuntimeCommand(runtime));
    runtime.insert("fixtureUrl",root);assert(overte::e2e::phoneWebRuntimeCommand(runtime));
    runtime.insert("action","feature-phone-web-reference-runtime-observe");assert(!overte::e2e::phoneWebRuntimeCommand(runtime));
    return 0;
}
'''
cpp=build/'world-web-contract.cpp';cpp.write_text(source)
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
jdk=Path('/usr/lib/jvm/java-21-temurin-jdk/include')
binary=build/'world-web-contract'
subprocess.run(['g++','-std=c++17','-fPIC','-I'+str(ROOT),'-I'+str(jdk),'-I'+str(jdk/'linux'),str(cpp),'-o',str(binary),*flags],check=True)
subprocess.run([str(binary)],check=True)
print('PASS: actual PhoneWorldWebBridge and PhoneWorldWebE2E provider compile/run with Qt6Core; item/JNI seams synthetic')
