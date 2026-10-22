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
#include <QCryptographicHash>
#include "libraries/shared/src/InlineHtmlDocument.h"
#include "libraries/shared/src/EmbeddedWebPolicy.h"
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
    QUrl original;overte::web::EmbeddedWebSession* observed{nullptr};
    quint64 generation() const { return observed ? observed->generation() : 1; }
    bool active() const { return observed ? observed->active() : true; }
    QUrl url() const { return observed ? observed->url() : original; }
    bool allowsBridge(quint64 grant,const QUrl& url,bool mainFrame,int bytes) const { return observed && observed->allowsBridge(grant,url,mainFrame,bytes); }
    bool allowsNavigation(quint64 grant,const QUrl& url,bool mainFrame,const QString& method) const { return observed && observed->allowsNavigation(grant,url,mainFrame,method); }
    bool allowsInlineResponse(quint64 grant,const QUrl& url,bool mainFrame,const QString& method) const { return observed && observed->allowsInlineResponse(grant,url,mainFrame,method); }
};
class NativeWebViewItem:public QObject {
public:
    enum Surface { Tablet,WorldEntity };
    Surface _surface{WorldEntity};Session _session;QUrl _document;mutable QMutex _mutex;
    jlong _handle{42};quint64 _page{1},_creationRevision{1},_featureWebFinishedGrant{1},_featureWebFinishedPage{1};
    QUrl _featureWebFinishedDocument;QString _sourceIdentity{"original-item"};
    quint64 _featureWebHTTPGrant{0},_featureWebHTTPPage{0};int _featureWebHTTPStatus{0};bool _inlineProvided{false};
    QString _url,_scriptUrl;overte::web::InlineHtmlDocument _inlineDocument;overte::web::EmbeddedWebSession security;
    struct Transport { int calls{0};void receive(const QJsonObject&) { ++calls; } } transport;
    Transport* _transport{&transport};
    static QVariantMap featurePhoneWorldWeb(const QVariantMap&);
    static void acceptFeatureWorldWebInput(const QString&,bool);
    void featureWorldWebRecord(const QString&,const QVariant& value={});
    bool featureTabletOwned(const QString&,const QString&) const;
    QVariantMap featureTabletInline() const;
    bool featureTabletIntercept(quint64,quint64,const QUrl&,const QUrl&,bool,const QByteArray&,const QJsonObject&);
    bool matchesOrigin(const QUrl&,const QUrl&) const;
    bool acceptMessage(quint64,quint64,const QUrl&,const QUrl&,bool,const QString&,const QByteArray&);
    bool current(quint64,quint64) const;
    QUrl sourceURL(const QUrl&) const;
    bool allowsBridgeDocument(quint64,quint64,const QUrl&) const;
    struct Mapping { QUrl toSource(const QUrl& url) const { return url; } } _mapping;
    bool _suspendedDocument{false},_inputFocused{false};quint64 _inputEpoch{0};QObject bridge;QObject* _bridge{&bridge};
    void updateEditor(const QJsonObject&) {}
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
// ACTUAL_NATIVE_BRIDGE_FUNCTIONS
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
    overte::web::InlineHtmlDocumentOwner owner;
    item._inlineProvided=true;item._inlineDocument=owner.issue(&app,"tablet:test","data:text/html,<p>original</p>");reference.insert("commandId",QString(32,'c'));
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
    registry.clear();item._inlineProvided=false;
    const QString tabletRun(32,'e'),tabletRoot="http://127.0.0.1:50001/feature-fixture/v1/runs/"+tabletRun+"/";
    QVariantMap tablet{{"schemaVersion",1},{"commandId",QString(32,'0')},{"action","phone-tablet-web"},
        {"runId",tabletRun},{"fixtureUrl",tabletRoot},{"ownerToken",QString(32,'1')},{"operation","reserve"}};
    assert(overte::e2e::phoneWorldWebCommand(tablet));
    assert(NativeWebViewItem::featurePhoneWorldWeb(tablet).value("status")=="ready");
    item._surface=NativeWebViewItem::Tablet;item._sourceIdentity="tablet:actual-fixture-owner";
    const auto html=("<meta name=\"overte-fixture-owner\" content=\""+tabletRun+"\"><p>original input</p>").toUtf8();
    item._url="data:text/html;charset=utf-8;base64,"+QString::fromLatin1(html.toBase64());item._scriptUrl=tabletRoot+"tickets/"+ticket+"/injected.js";
    item._inlineDocument=owner.issue(&app,item._sourceIdentity,item._url,item._scriptUrl);item._inlineProvided=true;
    item.security.setForeground(true);item.security.setVisible(true);item._session.observed=&item.security;
    const auto nativeGrant=item.security.openInline(item._inlineDocument,&app,item._url,overte::web::Surface::Tablet,item._sourceIdentity,item._scriptUrl);
    assert(nativeGrant && item.featureTabletOwned(tabletRun,tabletRoot));
    assert(!item.featureTabletOwned(run,root));
    item._session.original=item._inlineDocument.transportURL();item._document=item._session.original;
    registry.insert(42,&item);tablet.insert("operation","arm-held");tablet.insert("commandId",QString(32,'2'));
    assert(NativeWebViewItem::featurePhoneWorldWeb(tablet).value("status")=="ready");
    QJsonObject callback{{"type",6},{"object","eventBridge"},{"method","emitWebEvent"},{"args",QJsonArray{request}}};
    const auto callbackBytes=QJsonDocument(callback).toJson(QJsonDocument::Compact);const QUrl callbackOrigin=item._document.adjusted(QUrl::RemovePath);
    assert(!item.acceptMessage(nativeGrant,item._page,item._document,QUrl("http://foreign.invalid"),true,"channel",callbackBytes));
    assert(!item.acceptMessage(nativeGrant,item._page,QUrl("http://foreign.invalid/index.html"),callbackOrigin,true,"channel",callbackBytes));
    assert(!item.acceptMessage(nativeGrant+1,item._page,item._document,callbackOrigin,true,"channel",callbackBytes));
    assert(item.acceptMessage(nativeGrant,item._page,item._document,callbackOrigin,true,"channel",callbackBytes));
    QCoreApplication::processEvents();assert(worldWebScopes[tabletRun].heldPending && item.transport.calls==0);
    const auto held=worldWebScopes[tabletRun].held;assert(!held.isEmpty());
    tablet.insert("operation","retire");tablet.insert("commandId",QString(32,'3'));
    assert(NativeWebViewItem::featurePhoneWorldWeb(tablet).isEmpty()); // An actual held callback cannot be retired silently.
    const auto oldDocument=item._inlineDocument;
    owner.revoke();assert(!oldDocument.current());
    // A real replacement lease must not lend its new token/grant to the old callback.
    item._inlineDocument=owner.issue(&app,item._sourceIdentity,item._url,item._scriptUrl);
    assert(item._inlineDocument.current() && item._inlineDocument.token()!=held.value("token"));
    item.security.openInline(item._inlineDocument,&app,item._url,overte::web::Surface::Tablet,item._sourceIdentity,item._scriptUrl);
    item._session.original=item._inlineDocument.transportURL();item._document=item._session.original;++item._page;
    tablet.insert("operation","deliver-held");tablet.insert("commandId",QString(32,'4'));
    assert(NativeWebViewItem::featurePhoneWorldWeb(tablet).value("status")=="ready");
    const auto delivery=worldWebScopes[tabletRun].deliveries[0].toMap();
    for (auto entry=held.cbegin();entry!=held.cend();++entry) { assert(delivery.value(entry.key())==entry.value()); }
    assert(delivery.value("leaseCurrent")==false && delivery.value("accepted")==false && item.transport.calls==0);
    registry.clear();tablet.insert("operation","retire");tablet.insert("commandId",QString(32,'5'));
    assert(NativeWebViewItem::featurePhoneWorldWeb(tablet).value("status")=="ready");
    return 0;
}
'''
native=(ROOT/'android/common/web/src/NativeWebViewItem.cpp').read_text()
functions='\n'.join(native[native.index(start):native.index(end,native.index(start))] for start,end in (
    ('bool NativeWebViewItem::current(', 'bool NativeWebViewItem::allowsNavigation('),
    ('bool NativeWebViewItem::allowsBridgeDocument(', 'bool NativeWebViewItem::allowsEditorDocument('),
    ('bool NativeWebViewItem::acceptMessage(', 'void NativeWebViewItem::acceptState(')))
source=source.replace('// ACTUAL_NATIVE_BRIDGE_FUNCTIONS',functions)
cpp=build/'world-web-contract.cpp';cpp.write_text(source)
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
jdk=Path('/usr/lib/jvm/java-21-temurin-jdk/include')
binary=build/'world-web-contract'
subprocess.run(['g++','-std=c++17','-fPIC','-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(jdk),'-I'+str(jdk/'linux'),str(cpp),'-o',str(binary),*flags],check=True)
subprocess.run([str(binary)],check=True)
print('PASS: actual Phone browser provider/grammar and original native bridge entry compile/run with real inline leases; item/mapping/JNI/transport seams synthetic')
