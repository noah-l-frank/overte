// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "ChatEmptyHistoryLease.h"
#include "PhoneSnapshotSettingsKeys.h"
namespace overte::e2e {
// Values are captured inside the native owner. Host commands can name one
// original digest, never replacement keys, settings, paths or desired results.
class PhoneSnapshotSettingsLease {
public:
    bool retired() const { return _retired; }
    using Values=ChatEmptyHistoryLease;
    using Read=std::function<QVariantMap()>;
    using Restore=std::function<bool(const QVariantMap&,const QVariantMap&)>;
    static bool valid(const QVariantMap& state) {
        if (state.keys()!=QStringList{"entries","format"} || state.value("entries").userType()!=QMetaType::QVariantMap
                || state.value("format").userType()!=QMetaType::QVariantMap || Values::bytes(state).isEmpty()) { return false; }
        const auto entries=state.value("entries").toMap(),format=state.value("format").toMap();
        if (entries.keys()!=snapshotSettingsKeys() || format.keys()!=QStringList{"set","value"}
                || format.value("set").userType()!=QMetaType::Bool || format.value("value").userType()!=QMetaType::QString
                || format.value("value").toString().size()>16) { return false; }
        for (const auto& entry:entries) {
            if (entry.userType()!=QMetaType::QVariantMap || entry.toMap().keys()!=QStringList{"present","value"}
                    || entry.toMap().value("present").userType()!=QMetaType::Bool) { return false; }
        }
        return true;
    }
    static bool same(const QVariant& a,const QVariant& b) { return !Values::bytes(a).isEmpty() && Values::bytes(a)==Values::bytes(b); }
    static bool validCommand(const QVariantMap& input) {
        const auto command=QJsonObject::fromVariantMap(input);const auto fields=command.keys();
        const auto operation=command.value("operation").toString();
        QSet<QString> keys{"schemaVersion","commandId","action","runId","operation"};
        if (operation=="restore") { keys.insert("restoreId");keys.insert("expectedSha256"); }
        return QSet<QString>(fields.begin(),fields.end())==keys && command.value("schemaVersion")==QJsonValue(1)
            && command.value("action")==QJsonValue("phone-snapshot-settings") && nonce(command.value("runId").toString())
            && nonce(command.value("commandId").toString()) && QSet<QString>{"capture","observe","restore","retire"}.contains(operation)
            && (operation!="restore" || (nonce(command.value("restoreId").toString())
                && QRegularExpression("\\A[0-9a-f]{64}\\z").match(command.value("expectedSha256").toString()).hasMatch()));
    }
    static bool partial(const QVariantMap& actual,const QVariantMap& basis,const QVariantMap& original) {
        if (!valid(actual) || !valid(basis) || !valid(original)) { return false; }
        if (same(actual,basis) || same(actual,original)) { return true; }
        auto a=actual.value("entries").toMap(),b=basis.value("entries").toMap(),o=original.value("entries").toMap();
        const auto format=a.take("snapshotFormat"),bf=b.take("snapshotFormat"),of=o.take("snapshotFormat");
        const auto native=original.value("format").toMap();
        const QVariantMap normalized{{"present",native.value("set")},{"value",native.value("set").toBool()?native.value("value"):QVariant()}};
        return (same(a,b) || same(a,o)) && (same(format,bf) || same(format,of) || same(format,normalized))
            && (same(actual.value("format"),basis.value("format")) || same(actual.value("format"),original.value("format")));
    }
    QVariantMap request(const QVariantMap& input,bool closed,const Read& read,const Restore& restore) {
        const auto command=QJsonObject::fromVariantMap(input);
        const auto run=command.value("runId").toString(),id=command.value("commandId").toString(),operation=command.value("operation").toString();
        const bool restoring=operation=="restore";
        if (!QCoreApplication::arguments().contains("--testScript") || !read || !restore || !_available
                || !validCommand(input)
                || (!_run.isEmpty() && _run!=run) || (operation!="capture" && _run.isEmpty())) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch || _sequence>=9007199254740991ULL) { _available=false;return {}; }_epoch=now;
        auto actual=read();if (!valid(actual)) { return {}; }
        if (_retired && Values::digest(actual)!=_originalSha) { return {}; }
        if (operation=="capture") {
            if (!closed || _retired || _restoreStarted || (!_run.isEmpty() && !same(actual,_original))) { return {}; }
            if (_run.isEmpty()) { _run=run;_original=actual;_opened=now;_originalSha=Values::digest(actual); }
        } else if (restoring) {
            const auto restoreId=command.value("restoreId").toString(),expected=command.value("expectedSha256").toString();
            if (_run!=run || !closed || _retired || !nonce(restoreId)
                    || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(expected).hasMatch()) { return {}; }
            if (!_restoreStarted) {
                if (Values::digest(actual)!=expected) { return {}; }
                _restoreStarted=true;_restoreId=restoreId;_expectedSha=expected;_basis=actual;
            } else if (_restoreId!=restoreId || _expectedSha!=expected || !partial(actual,_basis,_original)) { return {}; }
            if (!_restored) {
                if (!restore(actual,_original)) { return {}; }
                actual=read();if (!valid(actual) || !same(actual,_original)) { return {}; }
                _handback=QDateTime::currentMSecsSinceEpoch();
                if (_handback<now) { _available=false;return {}; }
                _restored=true;
            } else if (!same(actual,_original)) { return {}; }
        } else if (operation=="retire") {
            if (_run!=run || !closed || !_restored || Values::digest(actual)!=_originalSha) { return {}; }
            _retired=true;_original.clear();_basis.clear(); // Release private typed originals; never revive this scope.
        }
        if (_restoreStarted && !_retired && !partial(actual,_basis,_original)) { _available=false;return {}; }
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        if (captured<now || captured-now>=1500) { _available=false;return {}; }_epoch=captured;
        return {{"snapshotSettingsLeaseVersion",2},{"instance",_instance},{"runId",run},{"commandId",id},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",captured},{"operation",operation},
            {"source",QVariantMap{{"scopePresent",!_run.isEmpty() && !_retired},{"closed",closed},{"restoring",_restoreStarted},
                {"restored",_restored},{"retired",_retired},{"openedEpochMs",_opened},{"handbackEpochMs",_handback},
                {"originalSha256",_originalSha},{"currentSha256",Values::digest(actual)},{"restoreId",_restoreId},
                {"expectedSha256",_expectedSha},{"current",actual},{"currentSerializedBase64",QString::fromLatin1(Values::bytes(actual).toBase64())}}}};
    }
private:
    static bool nonce(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QString _run,_originalSha,_restoreId,_expectedSha;QVariantMap _original,_basis;
    bool _available{true},_restoreStarted{false},_restored{false},_retired{false};
    qint64 _epoch{0},_opened{0},_handback{0};quint64 _sequence{0};
 };
// Restore the typed native cache through its original set/remove path, then
// restore exact raw key presence as well. Neither source can stand for the other.
inline bool restoreSnapshotSettings(const QVariantMap& expected,const QVariantMap& original,
        const PhoneSnapshotSettingsLease::Read& read,
        const std::function<bool(const QVariantMap&,const QVariantMap&)>& entries,
        const std::function<bool(const QVariantMap&)>& format) {
    using Lease=PhoneSnapshotSettingsLease;
    if (!read || !entries || !format || !Lease::valid(expected) || !Lease::valid(original)
            || !Lease::same(read(),expected) || !entries(expected.value("entries").toMap(),original.value("entries").toMap())
            || !format(original.value("format").toMap())) { return false; }
    const auto actual=read();if (!Lease::valid(actual) || !Lease::same(actual.value("format"),original.value("format"))) { return false; }
    auto current=actual.value("entries").toMap(),prior=original.value("entries").toMap();
    const auto observedFormat=current.take("snapshotFormat"),originalFormat=prior.take("snapshotFormat");
    const auto native=original.value("format").toMap();
    const QVariantMap normalized{{"present",native.value("set")},{"value",native.value("set").toBool()?native.value("value"):QVariant()}};
    if (!Lease::same(current,prior) || (!Lease::same(observedFormat,originalFormat) && !Lease::same(observedFormat,normalized))) { return false; }
    return entries(actual.value("entries").toMap(),original.value("entries").toMap()) && Lease::same(read(),original);
}
}
#endif
