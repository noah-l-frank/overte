// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QMap>
#include <QHash>
#include <QVariantMap>
#include <QSysInfo>
#include <QUuid>
#include <QVector>
#include <exception>
#include <memory>
#include "Node.h"
#include "AssetUtils.h"
#include "ClientServerUtils.h"
#include "ReceivedMessage.h"

namespace overte::e2e {
// Only explicitly registered independent readers are observed. This is not an
// inventory of product model consumers, uploads, servers or oven workers.
class IOSAssetReplyTrace {
public:
    static IOSAssetReplyTrace& instance(); // One out-of-line networking registry.
    static QString& current();
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QString sha(const QByteArray& bytes) {return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
    static QJsonObject bytes(const QByteArray& raw) {
        const bool retained=raw.size()<=65536;
        return {{"bytes",raw.size()},{"sha256",sha(raw)},{"retained",retained},
            {"base64",retained ? QJsonValue(QString::fromLatin1(raw.toBase64())) : QJsonValue(QJsonValue::Null)}};
    }
    bool add(QObject* object,const QVariantMap& query,const QJsonObject& inputs,const std::weak_ptr<void>& token) {
        if (!enabled() || !object) {return false;}QMutexLocker guard(&_mutex);
        const auto key=query.value("commandId").toString();
        if (_rows.size()>=64 || _rows.contains(key) || _objects.contains(object) || token.expired()) {return false;}
        Row row;row.object=object;row.query=query;row.inputs=inputs;row.token=token;row.identity=nonce();row.created=stamp();
        _rows.insert(key,row);_objects.insert(object,key);return true;
    }
    QString key(QObject* object) {QMutexLocker guard(&_mutex);return _objects.value(object);}
    bool tracks(const SharedNodePointer& server,MessageID message) {
        if (!enabled() || !server) {return false;}QMutexLocker guard(&_mutex);
        return _wires.contains(server->getUUID().toString(QUuid::WithoutBraces)+':'+QString::number(message));
    }
    QObject* live(const QString& key) {
        // Called only on the actual request's worker thread, without yielding.
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);return found!=_rows.end() && found->alive ? found->object : nullptr;
    }
    class Scope {
    public:
        explicit Scope(QObject* object):_previous(current()) {
            current()=enabled() ? instance().key(object) : QString();
            if (!current().isEmpty()) {instance().started(current());}
        }
        ~Scope() {current()=_previous;}
        Scope(const Scope&)=delete;Scope& operator=(const Scope&)=delete;
    private:QString _previous;
    };
    class Body {
    public:
        Body(QObject* object,const QString& kind,const QJsonObject& detail=QJsonObject()):_exceptions(std::uncaught_exceptions()) {
            if (enabled()) {_key=instance().key(object);if (!_key.isEmpty()) {_body=instance().enter(_key,kind,detail);}}
        }
        ~Body() {if (!_body.isEmpty()) {instance().leave(_key,_body,std::uncaught_exceptions()==_exceptions);}}
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:QString _key,_body;int _exceptions;
    };
    void sent(const QString& operation,const SharedNodePointer& server,MessageID message,const QUuid& domain,const QJsonObject& inputs) {
        if (!enabled() || current().isEmpty() || !server) {return;}QMutexLocker guard(&_mutex);auto found=_rows.find(current());if (found==_rows.end()) {return;}
        auto& row=found.value();const auto wire=server->getUUID().toString(QUuid::WithoutBraces)+':'+QString::number(message);
        if (!row.wire.isEmpty() || _wires.contains(wire) || !message || !server) {row.complete=false;return;}
        row.server=server;row.serverIdentity=nodeIdentity(server);row.wire=wire;_wires.insert(wire,current());
        append(row,"sent",{{"operation",operation},{"server",server->getUUID().toString(QUuid::WithoutBraces)},
            {"serverInstance",row.serverIdentity},{"messageId",static_cast<double>(message)},
            {"domainId",domain.toString(QUuid::WithoutBraces)},{"inputs",inputs}});
    }
    void mappingReply(const SharedNodePointer& server,MessageID message,int error,const QByteArray& payload,bool complete,bool failed) {
        if (!tracks(server,message)) {return;}
        reply(server,message,"mapping-reply",{{"serverError",error},{"payload",bytes(payload)},{"messageComplete",complete},{"messageFailed",failed}});
    }
    void observedMessage(const SharedNodePointer& server,MessageID wireMessage,const QString& kind,const QSharedPointer<ReceivedMessage>& actual) {
        if (!enabled() || !server || !actual) {return;}QMutexLocker guard(&_mutex);
        const auto wire=server->getUUID().toString(QUuid::WithoutBraces)+':'+QString::number(wireMessage);
        auto found=_rows.find(_wires.value(wire));if (found==_rows.end()) {return;}auto& row=found.value();
        for (const auto& original:row.messages) {if (original.actual.toStrongRef()==actual) {return;}}
        if (row.messages.size()>=4) {row.complete=false;return;}
        Message message;message.actual=actual;message.identity=nonce();message.kind=kind;message.observed=stamp();
        message.source=actual->getSourceID();message.type=static_cast<int>(actual->getType());message.version=actual->getVersion();
        row.messages.append(message);append(row,"message-observed",{{"messageObject",message.identity},{"kind",kind}});
    }
    void infoReply(const SharedNodePointer& server,MessageID message,int error,const QString& hash,qint64 size,qint64 messageBytes,bool complete,bool failed) {
        reply(server,message,"info-reply",{{"serverError",error},{"hash",hash},{"size",QString::number(size)},
            {"messageBytes",QString::number(messageBytes)},{"messageComplete",complete},{"messageFailed",failed}});
    }
    void rawHeader(const SharedNodePointer& server,MessageID message,int error,const QString& hash,qint64 length) {
        reply(server,message,"raw-header",{{"serverError",error},{"hash",hash},{"length",QString::number(length)}});
    }
    void rawBody(const SharedNodePointer& server,MessageID message,bool received,int error,const QByteArray& payload) {
        if (!tracks(server,message)) {return;}
        reply(server,message,"raw-body",{{"responseReceived",received},{"serverError",error},{"payload",bytes(payload)}});
    }
    void result(QObject* object,const QJsonObject& original) {
        if (!enabled()) {return;}QMutexLocker guard(&_mutex);auto found=_rows.find(_objects.value(object));if (found==_rows.end()) {return;}
        auto& row=found.value();if (!row.result.isEmpty() || row.bodies.isEmpty()) {row.complete=false;return;}
        row.result=original;const auto raw=QJsonDocument(original).toJson(QJsonDocument::Compact);
        row.resultBytes=raw;
        if (original.contains("complete") && original.value("complete")!=QJsonValue(true)
                || original.contains("body") && original.value("body").toObject().value("retained")!=QJsonValue(true)) {row.complete=false;}
        if (raw.size()>160000) {row.complete=false;row.result={};row.resultBytes.clear();}
        append(row,"result",{{"bytes",raw.size()},{"sha256",sha(raw)}});
    }
    void destroyed(const QString& key) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end()) {return;}auto& row=found.value();
        if (!row.alive) {row.complete=false;return;}_objects.remove(row.object);row.alive=false;append(row,"destroyed",{});
    }
    bool retireIssued(const QString& key) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end() || found->retireIssued) {return false;}
        found->retireIssued=true;append(found.value(),"retire-issued",{});return true;
    }
    void retiredQueueFailed(const QString& key) {QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found!=_rows.end()) {found->complete=false;}}
    QVariantMap read(const QString& key) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end()) {return {};}auto& row=found.value();
        QJsonArray messages;
        for (auto& message:row.messages) {
            const bool alive=!message.actual.isNull();
            if (!alive && message.expired.isEmpty()) {message.expired=stamp();append(row,"message-expired-observed",{{"messageObject",message.identity}});}
            messages.append(QJsonObject{{"messageObject",message.identity},{"kind",message.kind},{"sourceId",message.source},
                {"packetType",message.type},{"packetVersion",message.version},{"observed",message.observed},{"alive",alive},
                {"expired",message.expired.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(message.expired)}});
        }
        const bool tokenAlive=!row.token.expired();
        if (!tokenAlive && row.expired.isEmpty()) {row.expired=stamp();append(row,"token-expired-observed",{});}
        if (!tokenAlive && row.alive) {row.complete=false;}
        const auto now=stamp();
        return {{"iosAssetReplyTraceVersion",1},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clock",now.toVariantMap()},
            {"layout",QVariantMap{{"byteOrder",QSysInfo::ByteOrder==QSysInfo::LittleEndian ? "little" : "big"},
                {"messageIdBytes",static_cast<int>(sizeof(MessageID))},{"hashBytes",static_cast<int>(AssetUtils::SHA256_HASH_LENGTH)},
                {"bakingStatusBytes",static_cast<int>(sizeof(AssetUtils::BakingStatus))}}},
            {"complete",row.complete},{"job",QVariantMap{{"objectId",row.identity},{"request",row.query},{"inputs",row.inputs.toVariantMap()},
                {"created",row.created.toVariantMap()},{"alive",row.alive},{"pendingBodies",row.bodies.size()},
                {"messages",messages.toVariantList()},
                {"tokenAlive",tokenAlive},{"tokenExpired",row.expired.isEmpty() ? QVariant() : QVariant(row.expired.toVariantMap())},
                {"retireIssued",row.retireIssued},{"events",row.events.toVariantList()},
                {"result",row.result.isEmpty() ? QVariant() : QVariant(row.result.toVariantMap())},
                {"resultBase64",row.resultBytes.isEmpty() ? QVariant() : QVariant(QString::fromLatin1(row.resultBytes.toBase64()))}}}};
    }
private:
    struct Message {QWeakPointer<ReceivedMessage> actual;QString identity,kind;QJsonObject observed,expired;int source {0},type {0},version {0};};
    struct Row {
        QObject* object {nullptr};QVariantMap query;QJsonObject inputs,created,expired,result;QJsonArray events;QString identity,wire,serverIdentity;
        QByteArray resultBytes;
        std::weak_ptr<void> token;QWeakPointer<Node> server;QStringList bodies;bool complete {true},alive {true},started {false},retireIssued {false};
        QVector<Message> messages;
    };
    struct Peer {QWeakPointer<Node> node;QString identity;};
    IOSAssetReplyTrace() {_clock.start();}
    QJsonObject stamp() const {return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"monotonicMs",static_cast<double>(_clock.elapsed())}};}
    QString nodeIdentity(const SharedNodePointer& node) {
        for (const auto& peer:_peers) {if (peer.node.toStrongRef()==node) {return peer.identity;}}
        const auto id=nonce();_peers.append({node,id});return id;
    }
    void append(Row& row,const QString& kind,const QJsonObject& detail) {
        if (row.events.size()>=128) {row.complete=false;return;}
        row.events.append(QJsonObject{{"sequence",row.events.size()+1},{"eventId",nonce()},{"kind",kind},{"clock",stamp()},{"details",detail}});
    }
    void started(const QString& key) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end()) {return;}
        if (found->started) {found->complete=false;return;}found->started=true;append(found.value(),"started",{});
    }
    QString enter(const QString& key,const QString& kind,const QJsonObject& detail) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end()) {return {};}
        const auto id=nonce();found->bodies.append(id);append(found.value(),"callback-enter",{{"bodyId",id},{"callback",kind},{"original",detail}});return id;
    }
    void leave(const QString& key,const QString& body,bool normal) {
        QMutexLocker guard(&_mutex);auto found=_rows.find(key);if (found==_rows.end()) {return;}
        if (found->bodies.isEmpty() || found->bodies.last()!=body || !normal) {found->complete=false;return;}
        found->bodies.removeLast();append(found.value(),"callback-return",{{"bodyId",body},{"normal",normal}});
    }
    void reply(const SharedNodePointer& server,MessageID message,const QString& kind,QJsonObject detail) {
        if (!enabled() || !server) {return;}QMutexLocker guard(&_mutex);
        const auto wire=server->getUUID().toString(QUuid::WithoutBraces)+':'+QString::number(message);
        auto found=_rows.find(_wires.value(wire));if (found==_rows.end()) {return;}auto& row=found.value();
        const bool same=row.server.toStrongRef()==server;if (!same) {row.complete=false;}
        if (detail.contains("payload") && detail.value("payload").toObject().value("retained")!=QJsonValue(true)) {row.complete=false;}
        detail["sender"]=server->getUUID().toString(QUuid::WithoutBraces);detail["serverInstance"]=nodeIdentity(server);
        detail["messageObject"]=row.messages.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(row.messages.last().identity);
        detail["messageId"]=static_cast<double>(message);detail["sameTarget"]=same;append(row,kind,detail);
    }
    QMutex _mutex;QElapsedTimer _clock;QString _instance=nonce();quint64 _sequence {0};
    QMap<QString,Row> _rows;QHash<QObject*,QString> _objects;QMap<QString,QString> _wires;QVector<Peer> _peers;
};
} // namespace overte::e2e
#endif
