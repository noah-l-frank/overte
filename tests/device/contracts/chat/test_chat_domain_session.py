"""Real Qt5 original DomainHandler setters and MessagesClient source body.

Network I/O and NodeList transport are explicit seams; no domain/service runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from test_chat_settings_barrier import body

ROOT=Path(__file__).resolve().parents[4]
HARNESS=r'''
#include "tests/device/native/ChatDomainSession.h"
#include "tests/device/native/ChatObservation.h"
#include <QThread>
#include <QUrl>
#include <QLoggingCategory>
#include <QSharedPointer>
#include <cassert>
Q_LOGGING_CATEGORY(networking,"test.networking")
Q_LOGGING_CATEGORY(networking_ice,"test.networking.ice")
namespace overte::security {
enum class DiagnosticEvent{Redacted};const char* diagnosticEvent(DiagnosticEvent){return "synthetic logging seam";}
}
class DomainHandler:public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    void setUUID(const QUuid& uuid);void setIsConnected(bool isConnected);void disconnect(QString reason);
    GETTER
    bool requiresICE()const{return false;}
    void sendDisconnectPacket(){++unqualifiedPacketCalls;}
    int unqualifiedPacketCalls{0};QUuid _uuid,_connectionToken;bool _isConnected{false};
    int _lastDomainConnectionError{-1};QUrl _domainURL;
    struct Reset{void reset(){}}_icePeer;struct Clear{void clear(){}}_sockAddr;
    overte::e2e::ChatDomainSession _featureChatDomainSession;
signals:void connectedToDomain(QUrl);void disconnectedFromDomain();
};
SET_UUID
SET_CONNECTED
DISCONNECT
class FakeNode {
public:
    QMutex& getMutex(){return mutex;}QUuid getUUID()const{return id;}
    const void* getActiveSocket()const{return active?this:nullptr;}
    QMutex mutex;QUuid id{QUuid::createUuid()};bool active{true};
};
namespace NodeType{constexpr int MessagesMixer=4;}
class NodeList {
public:
    DomainHandler& getDomainHandler(){return domain;}
    QUuid getSessionUUID(){if(onSelf)onSelf();return self;}
    QSharedPointer<FakeNode> soloNodeOfType(int type){assert(type==4);if(onMixer)onMixer();return mixer;}
    DomainHandler domain;QUuid self{QUuid::createUuid()};QSharedPointer<FakeNode> mixer{new FakeNode};
    std::function<void()>onSelf,onMixer;
};
QSharedPointer<NodeList> nodes;
class DependencyManager {
public:
    static int reads;
    template<class T>static bool isSet(){return !nodes.isNull();}
    template<class T>static QSharedPointer<T>get(){++reads;return nodes;}
};
int DependencyManager::reads{0};
class MessagesClient:public QObject {
public:QVariantMap featureChatObservation(const QVariantMap& command);overte::e2e::ChatObservation _featureChat;
};
MESSAGES
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const auto run=QString(32,'a');
    const QUuid original("{11111111-2222-4333-8444-555555555555}"),other("{aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee}");
    DomainHandler actor;
    if (!QCoreApplication::arguments().contains("--testScript")) {
        actor.setUUID(original);actor.setIsConnected(true);
        assert(actor._uuid==original && actor._isConnected && actor.featureChatSession(run).isEmpty());
        MessagesClient ordinary;assert(ordinary.featureChatObservation({}).isEmpty());return 0;
    }
    assert(actor.featureChatSession(run).value("connected")==false);
    actor.setUUID(original);actor.setIsConnected(true);const auto first=actor.featureChatSession(run);
    assert(first.value("connected")==true && first.value("revision").toLongLong()==2);
    const auto expected=QString::fromLatin1(QCryptographicHash::hash(run.toUtf8()+':'+original.toRfc4122(),QCryptographicHash::Sha256).toHex());
    assert(first.value("domainSha256")==expected);
    actor.setIsConnected(true);assert(actor.featureChatSession(run)==first);
    actor.setUUID(other);actor.setUUID(original);const auto sameDomain=actor.featureChatSession(run);
    assert(sameDomain.value("domainSha256")==expected && sameDomain.value("revision").toLongLong()==4);
    actor.setIsConnected(false);actor.setIsConnected(true);
    assert(actor.featureChatSession(run).value("connectionBirth")!=first.value("connectionBirth"));
    actor.disconnect("unqualified network I/O seam");const auto disconnected=actor.featureChatSession(run);
    assert(disconnected.value("connected")==false && disconnected.value("domainSha256")==QString()
        && disconnected.value("connectionBirth")==QString() && disconnected.value("connectedEpochMs").toLongLong()==0);

    MessagesClient messages;
    assert(!nodes && messages.featureChatObservation({}).isEmpty() && !nodes && DependencyManager::reads==0);
    nodes.reset(new NodeList);nodes->domain.setUUID(original);nodes->domain.setIsConnected(true);
    auto command=[&](QString operation){return QVariantMap{{"schemaVersion",1},
        {"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"runId",run},{"action","feature-chat-observe"},{"operation",operation}};};
    const auto initial=messages.featureChatObservation(command("inspect")).value("source").toMap();
    assert(!initial.value("scopePresent").toBool() && !initial.value("retired").toBool()
        && initial.value("openedEpochMs").toLongLong()==0 && initial.value("eventSequence").toLongLong()==0
        && initial.value("events").toList().isEmpty());
    const auto received=messages.featureChatObservation(command("observe"));assert(received.value("chatVersion")==2);
    const auto session=received.value("source").toMap().value("session").toMap();assert(session.value("domainSha256")==expected);
    assert(session.value("instance")!=first.value("instance") && session.value("connectionBirth")!=first.value("connectionBirth"));
    assert(session.value("mixerActive")==true);
    nodes->mixer->active=false;assert(messages.featureChatObservation(command("inspect")).value("source").toMap().value("session").toMap().value("mixerActive")==false);
    nodes->mixer.clear();const auto absent=messages.featureChatObservation(command("inspect")).value("source").toMap();
    assert(absent.value("mixerPresent")==false && absent.value("session").toMap().value("domainSha256")==expected);
    bool raced{false};nodes->onSelf=[&]{if(!raced){raced=true;nodes->domain.setUUID(other);nodes->domain.setUUID(original);}};
    assert(messages.featureChatObservation(command("inspect")).isEmpty());nodes->onSelf={};
    nodes->mixer.reset(new FakeNode);int lookups{0};nodes->onMixer=[&]{if(++lookups==2)nodes->mixer.reset(new FakeNode);};
    assert(messages.featureChatObservation(command("inspect")).isEmpty());nodes->onMixer={};
    QJsonObject ordinary{{"action","send_chat_message"},{"channel","domain"},{"message","reply-"+run},
        {"displayName","explicit network seam"},{"position",QJsonObject{{"x",0.0},{"y",0.0},{"z",0.0}}}};
    const auto bytes=QString::fromUtf8(QJsonDocument(ordinary).toJson(QJsonDocument::Compact));
    messages._featureChat.received("chat",bytes,other,false);
    assert(messages.featureChatObservation(command("inspect")).value("source").toMap().value("eventSequence").toLongLong()==1);
    const auto retired=messages.featureChatObservation(command("retire")).value("source").toMap();
    assert(retired.value("retired").toBool() && !retired.value("scopePresent").toBool()
        && retired.value("openedEpochMs").toLongLong()==0 && retired.value("eventSequence").toLongLong()==0
        && retired.value("events").toList().isEmpty());
    messages._featureChat.received("chat",bytes,other,false);
    const auto passive=messages.featureChatObservation(command("inspect")).value("source").toMap();
    assert(passive.value("retired").toBool() && !passive.value("scopePresent").toBool()
        && passive.value("events").toList().isEmpty() && passive.value("session").toMap().value("connected").toBool());
    overte::e2e::ChatDomainSession badThread;badThread.changed(original,true,false);assert(badThread.snapshot(run).isEmpty());
    nodes.clear();const auto reads=DependencyManager::reads;
    assert(messages.featureChatObservation(command("inspect")).isEmpty());
    assert(!nodes && DependencyManager::reads==reads);
}
#include "test.moc"
'''


class DomainSessionTests(unittest.TestCase):
    def test_original_domain_assignments_connection_birth_and_messages_source(self):
        header=(ROOT/'libraries/networking/src/DomainHandler.h').read_text()
        domain=(ROOT/'libraries/networking/src/DomainHandler.cpp').read_text()
        messages=(ROOT/'libraries/networking/src/MessagesClient.cpp').read_text()
        self.assertIn('overte::e2e::ChatDomainSession _featureChatDomainSession;',header)
        program=HARNESS.replace('GETTER',body(header,'QVariantMap featureChatSession('))
        for tag,marker in (('SET_UUID','void DomainHandler::setUUID('),('SET_CONNECTED','void DomainHandler::setIsConnected('),('DISCONNECT','void DomainHandler::disconnect(')):
            program=program.replace(tag,body(domain,marker))
        program=program.replace('MESSAGES',body(messages,'QVariantMap MessagesClient::featureChatObservation('))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        moc=os.environ.get('OVERTE_CHAT_MOC') or shutil.which('moc-qt5') or shutil.which('moc')
        if not moc and os.environ.get('PKG_CONFIG_SYSROOT_DIR'):moc=str(Path(os.environ['PKG_CONFIG_SYSROOT_DIR'])/'usr/bin/moc-qt5')
        self.assertTrue(moc and Path(moc).is_file())
        with tempfile.TemporaryDirectory(prefix='overte-chat-domain-') as directory:
            unit=Path(directory)/'test.cpp';binary=Path(directory)/'test';unit.write_text(program)
            meta=subprocess.run([moc,'-DOVERTE_E2E_FEATURE_TESTS',str(unit),'-o',str(Path(directory)/'test.moc')],capture_output=True,text=True,timeout=20)
            self.assertEqual(0,meta.returncode,meta.stderr[:2500])
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(unit),'-o',str(binary),'-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            for arguments in ([],['--testScript']):
                executed=subprocess.run([str(binary),*arguments],capture_output=True,text=True,timeout=5)
                self.assertEqual(0,executed.returncode,executed.stderr[:2500])


if __name__=='__main__':unittest.main()
