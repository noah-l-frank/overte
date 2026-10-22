// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <SettingManager.h>
#include <QDataStream>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <cmath>
#include <utility>

namespace overte::e2e {
// Owns only the original two fixed Chat settings. Private variants never leave
// this native owner. This is storage restoration, not an Erase/input verdict or
// permission to retire the whole Chat journey's independent resource journals.
class ChatProfileOwner {
public:
    using View=std::function<QVariantMap(const QString&)>;
    ChatProfileOwner(Setting::Manager* manager,View view):_manager(manager),_view(std::move(view)) {}
    bool ownsManager(Setting::Manager* manager) const { return _manager && _manager==manager; }
    QVariantMap request(const QVariantMap& input) {
        if (!_manager || !_view || QThread::currentThread()!=_manager->thread()
                || !QCoreApplication::arguments().contains("--testScript") || !_valid) { return {}; }
        const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
        const auto run=object.value("runId").toString(),id=object.value("commandId").toString(),operation=object.value("operation").toString();
        const QRegularExpression hex("\\A[0-9a-f]{32}\\z");
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","runId","action","operation"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!=QJsonValue("feature-chat-profile")
                || !hex.match(run).hasMatch() || !hex.match(id).hasMatch()
                || (operation!="acquire" && operation!="inspect" && operation!="restore")
                || (!_run.isEmpty() && _run!=run) || _requests.contains(id) || _requests.size()>=4096) { return {}; }
        _requests.insert(id);_run=run;
        if ((operation=="acquire" && _owned) || (operation!="acquire" && !_owned)
                || (operation=="restore" && _restoreAttempted)) { return {}; }
        QElapsedTimer elapsed;elapsed.start();const auto started=QDateTime::currentMSecsSinceEpoch();
        const auto view=_view(run);
        if (!closed(view,run,started)) { return {}; }
        auto actual=_manager->featureChatSnapshot();auto hashes=fingerprint(actual);
        if (hashes.isEmpty() || (_owned && !sameOwner(actual))) { return {}; }
        if (operation=="acquire") {
            if (!empty(actual) || hashes.value("cache").toMap()!=hashes.value("worker").toMap()) { return {}; }
            _original=actual;_originalHashes=hashes;_owned=true;
        } else if (operation=="restore") {
            // Restore only our actual saved history, after the view has closed
            // and all original live/file history is empty. Config is never set.
            if (!empty(actual) || !configSame(hashes)) { return {}; }
            const auto original=_original.value("cache").toMap().value("ArmoredChat-Messages").toMap();
            _restoreAttempted=true; // Admission precedes the one original write.
            if (!_manager->featureChatRestoreHistory(actual,original)) { return {}; }
            actual=_manager->featureChatSnapshot();hashes=fingerprint(actual);
            if (hashes.isEmpty() || !sameOwner(actual)) { return {}; }
        }
        _restored=_restoreAttempted && hashes==_originalHashes;
        const auto finished=QDateTime::currentMSecsSinceEpoch();
        if (finished<started || finished<_epoch) { _valid=false;return {}; }
        if (elapsed.elapsed()>1500 || finished-started>1500 || _sequence>=9007199254740991LL) { return {}; }
        _epoch=finished;
        return {{"chatProfileVersion",1},{"commandId",id},{"runId",run},{"instance",_instance},{"sequence",++_sequence},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",finished},{"owned",_owned},
            {"restoreAttempted",_restoreAttempted},{"restored",_restored},{"original",_originalHashes},{"current",hashes},
            {"settings",QVariantMap{{"instance",actual.value("instance")},{"writerInstance",actual.value("writer").toMap().value("instance")},
                {"mutationSequence",actual.value("mutationSequence")},{"capturedEpochMs",actual.value("capturedEpochMs")}}},
            {"view",QVariantMap{{"instance",view.value("instance")},{"sequence",view.value("sequence")},{"capturedEpochMs",view.value("capturedEpochMs")}}}};
    }
private:
    static bool scalar(const QVariant& value) {
        if (!value.isValid() || value.isNull() || value.userType()==QMetaType::Bool) { return true; }
        if (value.userType()==QMetaType::QString) { return value.toString().size()<=256; }
        if (value.userType()!=QMetaType::Int && value.userType()!=QMetaType::UInt && value.userType()!=QMetaType::LongLong
                && value.userType()!=QMetaType::ULongLong && value.userType()!=QMetaType::Double) { return false; }
        const auto number=value.toDouble();return std::isfinite(number) && std::abs(number)<=9007199254740991.0;
    }
    static QString hash(const QVariantMap& row,bool history) {
        if (row.size()!=2 || row.value("present").userType()!=QMetaType::Bool || !row.contains("value")) { return {}; }
        const auto value=row.value("value");
        if (history) {
            if (!emptyValue(value)) { return {}; }
        } else if (value.userType()==QMetaType::QVariantMap) {
            const auto map=value.toMap();if (map.size()>32) { return {}; }
            for (auto it=map.cbegin();it!=map.cend();++it) { if (it.key().size()>128 || !scalar(it.value())) { return {}; } }
        } else if (!scalar(value)) { return {}; }
        QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream<<row.value("present").toBool()<<value;
        if (stream.status()!=QDataStream::Ok || bytes.size()>16384) { return {}; }
        return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
    }
    static bool emptyValue(const QVariant& value) {
        return !value.isValid() || value.isNull() || (value.userType()==QMetaType::QString && value.toString().isEmpty())
            || (value.userType()==QMetaType::QVariantList && value.toList().isEmpty())
            || (value.userType()==QMetaType::QStringList && value.toStringList().isEmpty());
    }
    static QVariantMap fingerprint(const QVariantMap& actual) {
        if (actual.value("settingsBarrierVersion")!=QVariant(2) || actual.value("pending")!=QVariant(qint64(0))) { return {}; }
        const auto cache=actual.value("cache").toMap(),writer=actual.value("writer").toMap(),values=writer.value("values").toMap();
        QVariantMap cacheHashes,workerHashes;
        for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
            // During inspection a nonempty run history is deliberately not
            // fingerprinted/admitted as restorable storage. The owner remains.
            const bool history=QString::fromLatin1(key)=="ArmoredChat-Messages";
            const auto c=hash(cache.value(key).toMap(),history),w=hash(values.value(key).toMap(),history);
            if (c.isEmpty() || w.isEmpty()) { return {}; }cacheHashes.insert(key,c);workerHashes.insert(key,w);
        }
        const auto physical=writer.value("physical").toMap();
        if (physical.size()!=2) { return {}; }
        for (const auto key:{"ArmoredChat-Messages","ArmoredChat-Config"}) {
            const auto row=physical.value(key).toMap();
            if (row.value("present").userType()!=QMetaType::Bool
                    || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(row.value("sha256").toString()).hasMatch()) { return {}; }
        }
        return {{"cache",cacheHashes},{"worker",workerHashes},{"physical",physical}};
    }
    static bool empty(const QVariantMap& actual) {
        return actual.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Messages").toMap().value("empty")==QVariant(true);
    }
    static bool closed(const QVariantMap& view,const QString& run,qint64 started) {
        const auto source=view.value("source").toMap(),keyboard=source.value("keyboard").toMap(),ui=source.value("ui").toMap();
        const auto captured=view.value("capturedEpochMs").toLongLong();
        return view.value("chatViewVersion")==QVariant(2) && view.value("processId").toLongLong()==QCoreApplication::applicationPid()
            && view.value("runId")==QVariant(run) && captured>=started && captured-started<=1500
            && source.value("editorFocused")==QVariant(false) && source.value("editorHasDraft")==QVariant(false)
            && keyboard.value("available")==QVariant(true) && keyboard.value("visible")==QVariant(false)
            && ui.value("present")==QVariant(false);
    }
    bool sameOwner(const QVariantMap& actual) const {
        return actual.value("instance")==_original.value("instance")
            && actual.value("writer").toMap().value("instance")==_original.value("writer").toMap().value("instance")
            && actual.value("mutationSequence").toLongLong()>=_original.value("mutationSequence").toLongLong();
    }
    bool configSame(const QVariantMap& hashes) const {
        for (const auto source:{"cache","worker","physical"}) {
            if (hashes.value(source).toMap().value("ArmoredChat-Config")!=_originalHashes.value(source).toMap().value("ArmoredChat-Config")) { return false; }
        }return true;
    }
    QPointer<Setting::Manager> _manager;View _view;QSet<QString> _requests;QString _run;
    QVariantMap _original,_originalHashes;bool _owned{false},_restoreAttempted{false},_restored{false},_valid{true};
    qint64 _sequence{0},_epoch{0};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
}
#endif
