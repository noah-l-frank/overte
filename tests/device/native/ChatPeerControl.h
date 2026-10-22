// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>
#include <atomic>
#include <cmath>
#include <functional>
namespace overte::e2e {
// Dedicated fixture peer inputs only. The ordinary Messages send callback is
// never a receipt. ChatObservation independently records actual received data.
// The original fixture update pauses its own trajectory while this lease lives.
class ChatPeerControl {
public:
    using Read=std::function<QVariantMap()>;
    using Write=std::function<void(const QVariantMap&)>;
    using Send=std::function<void(const QString&)>;
    bool configure(Read read,Write write,Send send) {
        if (_read || !read || !write || !send || !QCoreApplication::arguments().contains("--testScript")) { return false; }
        _read=read;_write=write;_send=send;return true;
    }
    bool leased() const { return _leased.load(); }
    QVariantMap request(const QVariantMap& input,const QString& instance,const QUuid& self,const QUuid& mixer) {
        const QSet<QString> operations{"inspect","lease","send-domain-reply","send-domain-hidden","send-local-reply","send-local-distant","restore"};
        const auto json=QJsonObject::fromVariantMap(input);const auto keys=json.keys();
        const auto run=json.value("runId").toString(),id=json.value("commandId").toString(),operation=json.value("operation").toString();
        if (!_read || !_write || !_send || !QCoreApplication::arguments().contains("--testScript") || !_available || self.isNull()
                || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","operation","runId"}
                || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-chat-peer")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(instance).hasMatch()
                || !operations.contains(operation) || (!_run.isEmpty() && _run!=run)) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch || _sequence>=9007199254740991ULL) { _available=false;return {}; }_epoch=now;
        auto position=_read();if (!pose(position)) { return {}; }
        if (operation=="lease") {
            if (_restored) { return {}; }
            if (_run.isEmpty()) { _run=run;_leased.store(true);_settling=now;_settled=position; }
        }
        if (_leased.load() && !_admitted) {
            if (position!=_settled) { _settled=position;_settling=now; }
            if (now-_settling>=100) { _original=position;_ownedPosition=position;_admitted=true; }
        }
        if (operation.startsWith("send-")) {
            if (!_leased.load() || !_admitted || mixer.isNull() || _inputs>=64 || _used.contains(operation) || position!=_ownedPosition) { return {}; }
            _used.insert(operation); // Consume before any pose or network mutation; uncertain sends never replay.
            const bool distant=operation=="send-local-distant";
            auto target=_original;if (distant) { target["x"]=static_cast<double>(static_cast<float>(target.value("x").toDouble()+128.0)); }
            _ownedPosition=target;_write(target);position=_read();if (!pose(position) || position!=target) { return {}; }
            const auto channel=operation.startsWith("send-local-")?QString("local"):QString("domain");
            const auto text=(operation.endsWith("hidden") || distant?QString("hidden-"):QString("reply-"))+run;
            const QJsonObject payload{{"action","send_chat_message"},{"channel",channel},{"message",text},
                {"displayName","OVERTE_E2E_PEER"},{"position",QJsonObject::fromVariantMap(position)}};
            const auto bytes=QJsonDocument(payload).toJson(QJsonDocument::Compact);
            // Persist original consumed input and actual pose before entering
            // the ordinary network method. No message event is inserted here.
            _lastInput={{"sequence",static_cast<qulonglong>(++_inputs)},{"operation",operation},{"capturedEpochMs",now},
                {"position",position},{"payloadSha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}};
            _send(QString::fromUtf8(bytes));
        } else if (operation=="restore") {
            if (!_admitted || _run!=run) { return {}; }
            if (!_restored) {
                if (!_leased.load() || position!=_ownedPosition) { return {}; }
                _ownedPosition=_original;_write(_original);const auto actual=_read();if (!pose(actual) || actual!=_original) { return {}; }
                _handback={{"capturedEpochMs",now},{"position",actual},{"inputSequence",static_cast<qulonglong>(_inputs)}};
                _restored=true;_leased.store(false);
            }
            position=_read();if (!pose(position)) { return {}; }
        }
        const auto identity=[&](const QUuid& uuid) { return QString::fromLatin1(QCryptographicHash::hash(run.toUtf8()+':'+uuid.toRfc4122(),QCryptographicHash::Sha256).toHex()); };
        return {{"chatPeerVersion",1},{"commandId",id},{"runId",run},{"operation",operation},{"instance",instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},
            {"source",QVariantMap{{"selfSha256",identity(self)},{"mixerPresent",!mixer.isNull()},{"mixerSha256",mixer.isNull()?QString():identity(mixer)},
                {"leasePresent",_leased.load()},{"admitted",_admitted},{"restored",_restored},{"position",position},
                {"originalPosition",_original},{"inputSequence",static_cast<qulonglong>(_inputs)},{"lastInput",_lastInput},{"handback",_handback}}}};
    }
private:
    static bool pose(const QVariantMap& value) {
        if (value.keys()!=QStringList{"x","y","z"}) { return false; }
        for (auto it=value.cbegin();it!=value.cend();++it) {
            const auto type=it.value().userType();bool okay{false};const auto coordinate=it.value().toDouble(&okay);
            if (type==QMetaType::Bool || type==QMetaType::QString || !okay || !std::isfinite(coordinate) || std::abs(coordinate)>1000000) { return false; }
        }
        return true;
    }
    Read _read;Write _write;Send _send;std::atomic<bool> _leased{false};bool _available{true},_admitted{false},_restored{false};
    QString _run;QSet<QString> _used;QVariantMap _original,_ownedPosition,_settled,_lastInput,_handback;qint64 _epoch{0},_settling{0};quint64 _sequence{0},_inputs{0};
};
} // namespace overte::e2e
#endif
