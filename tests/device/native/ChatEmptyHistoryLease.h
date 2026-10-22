// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QDateTime>
#include <QJsonObject>
#include <QIODevice>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>
#include <functional>
namespace overte::e2e {
// This fixture profile admits an actually empty original history only. Normal
// Erase clears the running script's history first; this lease restores only
// the original empty variant/presence after actual editor/keyboard closure.
class ChatEmptyHistoryLease {
public:
    using Read=std::function<QVariantMap()>;
    using Restore=std::function<bool(const QVariantMap&,const QVariantMap&)>;
    static QString kind(const QVariantMap& state) {
        if (!state.value("historyPresent").toBool()) { return "unset"; }
        const auto value=state.value("history");
        if (!value.isValid() || value.isNull()) { return "null"; }
        if (value.userType()==QMetaType::QString && value.toString().isEmpty()) { return "empty-string"; }
        if (value.userType()==QMetaType::QVariantList && value.toList().isEmpty()) { return "array"; }
        if (value.userType()==QMetaType::QStringList && value.toStringList().isEmpty()) { return "string-list"; }
        return {};
    }
    static QByteArray bytes(const QVariant& value) {
        QByteArray result;QDataStream stream(&result,QIODevice::WriteOnly);stream<<value;
        return stream.status()==QDataStream::Ok && result.size()<=32768?result:QByteArray();
    }
    static QString digest(const QVariant& value) {
        const auto raw=bytes(value);return raw.isEmpty()?QString():QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());
    }
    QVariantMap request(const QVariantMap& input,bool closed,const Read& read,const Restore& restore) {
        const auto command=QJsonObject::fromVariantMap(input);const auto keys=command.keys();
        const auto run=command.value("runId").toString(),id=command.value("commandId").toString(),operation=command.value("operation").toString();
        if (!QCoreApplication::arguments().contains("--testScript") || !read || !restore || !_available
                || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","operation","runId"}
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue("feature-chat-history")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QSet<QString>{"inspect","capture","restore","retire"}.contains(operation)
                || (!_run.isEmpty() && _run!=run)) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch || _sequence>=9007199254740991ULL) { _available=false;return {}; }_epoch=now;
        auto actual=read();if (!valid(actual)) { return {}; }
        const auto config=digest(QVariantMap{{"present",actual.value("configPresent")},{"value",actual.value("config")}});
        if (config.isEmpty() || (!_run.isEmpty() && config!=_config)) { return {}; }
        if (operation=="capture") {
            if (!closed || _retired || _restored || kind(actual).isEmpty()) { return {}; }
            if (_run.isEmpty()) {
                _run=run;_original=actual;_originalKind=kind(actual);_originalSha=digest(actual);_config=config;_opened=now;
                if (_originalSha.isEmpty()) { return {}; }
            }
        } else if (operation=="restore") {
            if (_run!=run || !closed || _retired || kind(actual).isEmpty()) { return {}; }
            if (!_restored) {
                if (kind(actual)!="null" || !restore(actual,_original)) { return {}; }
                actual=read();if (!valid(actual) || digest(actual)!=_originalSha) { return {}; }
                _restored=true;_handback=now;
            } else if (digest(actual)!=_originalSha) { return {}; }
        } else if (operation=="retire") {
            if (_run!=run || !closed || !_restored || digest(actual)!=_originalSha) { return {}; }
            _retired=true;_original.clear(); // Release original private configuration.
        }
        const auto current=digest(actual);if (current.isEmpty()) { return {}; }
        return {{"chatHistoryVersion",1},{"commandId",id},{"runId",run},{"operation",operation},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},
            {"source",QVariantMap{{"scopePresent",!_run.isEmpty() && !_retired},{"retired",_retired},{"restored",_restored},
                {"originalKind",_originalKind},{"originalSha256",_originalSha},{"currentSha256",current},{"configSha256",config},
                {"openedEpochMs",_opened},{"handbackEpochMs",_handback},{"closed",closed}}}};
    }
private:
    static bool valid(const QVariantMap& value) {
        return value.keys()==QStringList{"config","configPresent","history","historyPresent"}
            && value.value("historyPresent").userType()==QMetaType::Bool && value.value("configPresent").userType()==QMetaType::Bool;
    }
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QString _run,_originalKind,_originalSha,_config;QVariantMap _original;
    bool _available{true},_restored{false},_retired{false};qint64 _epoch{0},_opened{0},_handback{0};quint64 _sequence{0};
};
} // namespace overte::e2e
#endif
