// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QByteArray>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QStringList>
#include <QThread>
#include <QUrl>
#include <QUuid>
#include <QVariantMap>
#include <functional>
#include <memory>

namespace overte::e2e {
// This source only calls the existing passive original getters. It owns no
// QWidget/WK callback, input, queue pump or resource-retirement mechanism.
// Original WorldDOM retains its real callback lease independently of status.
class IOSWorldWebSnapshotObservation {
public:
    using Reader=std::function<QVariantMap(const QString&,const QVariantMap&)>;
    IOSWorldWebSnapshotObservation() { _clock.start(); }
    static bool command(const QVariantMap& value) {
        const auto keys=value.keys();const auto json=QJsonObject::fromVariantMap(value);
        const auto run=value.value("runId").toString(),root=value.value("fixtureUrl").toString();
        const QUrl url(root,QUrl::StrictMode);
        return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl"}
            && json.value("schemaVersion")==QJsonValue(1) && json.value("action")==QJsonValue("feature-ios-world-web-snapshot")
            && QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(value.value("commandId").toString()).hasMatch()
            && QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            && root.size()<=512 && url.isValid() && (url.scheme()=="http" || url.scheme()=="https") && !url.host().isEmpty()
            && url.userName().isEmpty() && url.password().isEmpty() && !url.hasQuery() && !url.hasFragment()
            && url.path()=="/feature-fixture/v1/runs/"+run+"/" && url.toString(QUrl::FullyEncoded)==root;
    }
    QVariantMap read(const QVariantMap& request,const Reader& reader) {
        const auto app=QCoreApplication::instance();
        if (!app || QThread::currentThread()!=app->thread() || !QCoreApplication::arguments().contains("--testScript")
                || !command(request) || !reader) { return {}; }
        const auto id=request.value("commandId").toString();auto row=_records.value(id);
        if (!row) {
            if (!_complete || _records.size()>=512 || _sequence>=1000000000) { _complete=false;return {}; }
            int pending=0;for (const auto& old:_records) { if (old->status=="pending") { ++pending; } }
            if (pending>=8) { _complete=false;return {}; }
            row=std::make_shared<State>();row->request=request;row->sequence=++_sequence;row->before=clock();row->after=row->before;
            _records.insert(id,row);for (const auto& name:actions().keys()) { row->queries[name]=QVariant();row->selected[name]=QVariant(); }
            if (!call(*row,"ledgerBefore",reader)) { return packet(*row); }
            const auto found=current(row->last.value("ledgerBefore").toMap());
            if (found<0) { fail(*row);return packet(*row); }
            row->document=found>0;
        } else if (QJsonObject::fromVariantMap(row->request)!=QJsonObject::fromVariantMap(request)) { return {}; }
        if (row->status!="pending") { return packet(*row); }
        if (elapsed(*row)>=1500) { fail(*row);return packet(*row); }
        if (row->document) {
            // Same actual inner nonce on every poll. The existing DOM getter
            // schedules once and owns the original completion and weak owner.
            if (!call(*row,"document",reader)) { return packet(*row); }
            const auto dom=row->last.value("document").toMap();const auto status=dom.value("status").toString();
            if (status=="pending") { encode(*row);return packet(*row); }
            if (status!="ready") { fail(*row);return packet(*row); }
        } else { row->queries["document"]=QVariant();row->selected["document"]=QVariant(); }
        for (const auto* name:{"world","work","geometry","keys","pointer","entities","ledgerAfter"}) {
            if (!call(*row,QString::fromLatin1(name),reader)) { return packet(*row); }
        }
        row->after=clock();
        if (!encode(*row)) { return packet(*row); }
        row->status="ready";row->calls.clear();row->last.clear();
        // Keep only two complete bodies. Every known nonce remains recorded;
        // an evicted one is explicitly unavailable, never captured again.
        _completed.append(id);
        while (_completed.size()>2) {
            const auto old=_records.value(_completed.takeFirst());if (old) { old->payload.clear();old->status="unavailable"; }
        }
        const auto result=packet(*row);
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>2097152) { fail(*row);return packet(*row); }
        return result;
    }
private:
    struct State {
        QVariantMap request,before,after,queries,selected,last,payload;QVariantList calls;
        quint64 sequence{0};QString status{"pending"};bool document{false};
    };
    QVariantMap clock() const { return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"monotonicMs",static_cast<double>(_clock.elapsed())}}; }
    qint64 elapsed(const State& row) const { return _clock.elapsed()-row.before.value("monotonicMs").toLongLong(); }
    static QString sha(const QByteArray& value) { return QString::fromLatin1(QCryptographicHash::hash(value,QCryptographicHash::Sha256).toHex()); }
    static QString nonce() { return "ios-"+QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static QHash<QString,QString> actions() {
        return {{"ledgerBefore","feature-ios-world-web"},{"document","feature-ios-world-web-dom"},{"world","feature-ios-emote-world"},
            {"work","feature-ios-world-web-work"},{"geometry","feature-ios-world-web-geometry"},{"keys","feature-ios-world-web-keys"},
            {"pointer","feature-ios-pointer-state"},{"entities","feature-ios-create-entities"},{"ledgerAfter","feature-ios-world-web"}};
    }
    QVariantMap identityOf(const State& row) const {
        return {{"iosWorldWebSnapshotVersion",1},{"commandId",row.request.value("commandId")},{"runId",row.request.value("runId")},
            {"fixtureUrl",row.request.value("fixtureUrl")},{"instance",_instance},{"sequence",static_cast<double>(row.sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clockDomain","native-main-ios-world-web-snapshot"},
            {"clockBefore",row.before},{"clockAfter",row.after}};
    }
    QVariantMap packet(const State& row) const {
        auto result=identityOf(row);result["status"]=row.status;result["complete"]=_complete;
        result["payload"]=(row.status=="ready" || row.status=="pending")?QVariant(row.payload):QVariant();return result;
    }
    bool encode(State& row) {
        const QVariantMap body{{"iosWorldWebSnapshotBodyVersion",1},{"identity",identityOf(row)},{"queries",row.queries},
            {"calls",row.calls},{"originals",row.selected}};
        const auto plain=QJsonDocument::fromVariant(body).toJson(QJsonDocument::Compact);
        if (plain.size()>8*1024*1024 || elapsed(row)>=1500) { fail(row);return false; }
        const auto compressed=qCompress(plain,6);
        if (compressed.size()>1500000 || elapsed(row)>=1500) { fail(row);return false; }
        row.payload={{"encoding","qt-zlib-base64"},{"plainBytes",plain.size()},{"plainSha256",sha(plain)},
            {"compressedBytes",compressed.size()},{"compressedSha256",sha(compressed)},
            {"data",QString::fromLatin1(compressed.toBase64())}};
        return true;
    }
    void fail(State& row) { row.status="unavailable";row.after=clock();row.payload.clear();row.calls.clear();row.last.clear(); }
    bool call(State& row,const QString& name,const Reader& reader) {
        if (row.calls.size()>=64 || elapsed(row)>=1500) { fail(row);return false; }
        if (row.queries.value(name).isNull()) {
            QVariantMap query{{"schemaVersion",1},{"commandId",nonce()},{"action",actions().value(name)},{"runId",row.request.value("runId")}};
            if (name=="ledgerBefore" || name=="ledgerAfter" || name=="document") { query["fixtureUrl"]=row.request.value("fixtureUrl"); }
            row.queries[name]=query;
        }
        const auto query=row.queries.value(name).toMap(),before=clock(),original=reader(name,query),after=clock();
        row.after=after;
        if (original.isEmpty()) { fail(row);return false; }
        // A global legacy key source must never be put in this new raw file.
        if (name=="keys" && (QJsonObject::fromVariantMap(original).value("iosWorldWebKeysVersion")!=QJsonValue(2)
                || QJsonObject::fromVariantMap(original.value("source").toMap()).value("iosWorldWebKeySourceVersion")!=QJsonValue(2))) { fail(row);return false; }
        const auto raw=QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact);
        const int limit=(name=="ledgerBefore" || name=="ledgerAfter")?2097152:
            (name=="keys" || name=="pointer" || name=="entities")?1048576:262144;
        if (raw.size()>limit || (name=="document" && original.value("status")=="pending" && raw.size()>8192)) { fail(row);return false; }
        row.calls.append(QVariantMap{{"ordinal",row.calls.size()+1},{"name",name},{"command",query},{"clockBefore",before},
            {"clockAfter",after},{"resultJSON",QString::fromUtf8(raw)}});
        row.selected[name]=row.calls.size();row.last[name]=original;return true;
    }
    static int current(const QVariantMap& ledger) {
        if (ledger.isEmpty() || !ledger.value("complete").toBool()) { return -1; }
        QSet<QString> active;QHash<QString,QVariantMap> verified;
        for (const auto& value:ledger.value("events").toList()) {
            const auto row=value.toMap(),identity=row.value("identity").toMap();const auto kind=row.value("kind").toString();
            const auto key=identity.value("handle").toString()+":"+identity.value("creation").toString();
            if (kind=="view-created") { active.insert(key); }
            else if (kind=="view-teardown") { active.remove(key);verified.remove(key); }
            else if (kind=="document-began") { verified.remove(key); }
            else if (kind=="document-verified") { verified[key]=identity; }
        }
        int count=0;for (const auto& key:active) { if (verified.contains(key)) { ++count; } }
        return count>1?-1:count;
    }
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    quint64 _sequence{0};bool _complete{true};QElapsedTimer _clock;
    QHash<QString,std::shared_ptr<State>> _records;QStringList _completed;
};
} // namespace overte::e2e
#endif
