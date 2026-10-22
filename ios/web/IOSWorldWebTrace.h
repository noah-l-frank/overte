// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QVariant>
#include <functional>
#include <utility>

namespace overte::ios::world_web_trace {
using Function = std::function<QVariantMap(const QVariantMap&)>;
struct Provider final : Function { using Function::Function; };
inline const char* providerProperty() { return "_overteE2EIOSWorldWebProviderV1"; }
inline const char* domProviderProperty() { return "_overteE2EIOSWorldWebDOMProviderV1"; }
inline QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
inline QString codeSha256(const QString& code) { return QString::fromLatin1(QCryptographicHash::hash(code.toUtf8(),QCryptographicHash::Sha256).toHex()); }
inline bool enabled() {
    if (!QCoreApplication::instance()) { return false; }
    const auto args=QCoreApplication::arguments();
    const auto script=args.indexOf("--testScript"),result=args.indexOf("--testResultsLocation");
    return script>=0 && script+1<args.size() && !args[script+1].isEmpty()
        && result>=0 && result+1<args.size() && !args[result+1].isEmpty();
}
inline bool mainThread() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread(); }
inline bool command(const QVariantMap& value) {
    const auto json=QJsonObject::fromVariantMap(value);const auto fields=json.keys();
    const auto root=json.value("fixtureUrl").toString(),run=json.value("runId").toString();
    const QUrl url(root,QUrl::StrictMode);
    return QSet<QString>(fields.begin(),fields.end())==QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl"}
        && json.value("schemaVersion")==QJsonValue(1) && json.value("action")==QJsonValue("feature-ios-world-web")
        && QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(json.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
        && root.size()<=512 && !root.contains(QRegularExpression("[\\x00-\\x20\\x7f]"))
        && url.isValid() && (url.scheme()=="http" || url.scheme()=="https") && !url.host().isEmpty()
        && url.userInfo().isEmpty() && !url.hasQuery() && !url.hasFragment()
        && url.path()=="/feature-fixture/v1/runs/"+run+"/" && url.toString(QUrl::FullyEncoded)==root;
}
inline bool domCommand(const QVariantMap& value) {
    auto ledger=value;
    if (value.value("action")!="feature-ios-world-web-dom") { return false; }
    ledger["action"]="feature-ios-world-web";return command(ledger);
}
// Only actual native source URLs can introduce event ownership. A read request
// cannot create a view, label an old event, set a status or reset this ledger.
inline QString rootFor(const QVariantMap& identity) {
    if (identity.value("surface")!="world-entity") { return {}; }
    const auto source=identity.value("sourceUrl").toString();const QUrl url(source,QUrl::StrictMode);
    static const QRegularExpression path("\\A(/feature-fixture/v1/runs/[0-9a-f]{32}/)tickets/[0-9a-f]{32}/(?:index|reference)\\.html\\z");
    const auto match=path.match(url.path());
    if (!url.isValid() || !match.hasMatch() || (url.scheme()!="http" && url.scheme()!="https")
            || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()
            || url.toString(QUrl::FullyEncoded)!=source) { return {}; }
    auto root=url;root.setPath(match.captured(1));return root.toString(QUrl::FullyEncoded);
}
struct State {
    QMutex mutex;
    const QString instance { nonce() };
    QElapsedTimer timer;
    quint64 sequence { 0 },eventSequence { 0 };
    qint64 lastEpoch { 0 },lastMonotonic { 0 };
    bool complete { true };
    QVariantList events;
    State() { timer.start(); }
};
inline State& state() { static State actual;return actual; }
inline QVariantMap clock(State& actual) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.lastEpoch || mono<actual.lastMonotonic
            || (actual.lastEpoch && qAbs((epoch-actual.lastEpoch)-(mono-actual.lastMonotonic))>250)) { actual.complete=false; }
    actual.lastEpoch=epoch;actual.lastMonotonic=mono;
    return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline quint64 event(const QVariantMap& identity,const QString& kind,const QVariantMap& detail={}) {
    if (!enabled() || rootFor(identity).isEmpty()) { return 0; }
    auto& actual=state();QMutexLocker guard(&actual.mutex);
    if (!mainThread() || actual.events.size()>=2048 || actual.eventSequence>=9007199254740991ULL
            || QJsonDocument(QJsonObject::fromVariantMap(detail)).toJson(QJsonDocument::Compact).size()>32768) { actual.complete=false;return 0; }
    const auto stamp=clock(actual);const auto ordinal=++actual.eventSequence;
    actual.events.push_back(QVariantMap{{"sequence",static_cast<qulonglong>(ordinal)},{"eventId",nonce()},
        {"kind",kind},{"clock",stamp},{"identity",identity},{"detail",detail}});
    return ordinal;
}
// Construct inside the ORIGINAL completion body. Merely destroying the native
// block capture does not invoke this object and cannot claim callback return.
class Callback final {
public:
    Callback(QVariantMap identity,quint64 entry,QVariantMap result={}) : _identity(std::move(identity)),_entry(entry) {
        if (_entry) { event(_identity,"callback-enter",{{"entry",static_cast<qulonglong>(_entry)},{"result",result}}); }
    }
    ~Callback() { if (_entry) { event(_identity,"callback-return",{{"entry",static_cast<qulonglong>(_entry)}}); } }
    Callback(const Callback&)=delete;
    Callback& operator=(const Callback&)=delete;
private:
    QVariantMap _identity;
    quint64 _entry;
};
class Signal final {
public:
    Signal(QVariantMap identity,QString kind,QVariantMap detail) : _identity(std::move(identity)) {
        _entry=event(_identity,kind,detail);
    }
    ~Signal() { if (_entry) { event(_identity,"signal-return",{{"entry",static_cast<qulonglong>(_entry)}}); } }
private:
    QVariantMap _identity;
    quint64 _entry { 0 };
};
inline QVariantMap observe(const QVariantMap& query) {
    if (!enabled() || !mainThread() || !command(query)) { return {}; }
    auto& actual=state();QMutexLocker guard(&actual.mutex);const auto before=clock(actual);
    QVariantList events;
    const auto root=query.value("fixtureUrl").toString();
    for (const auto& entry:actual.events) {
        if (rootFor(entry.toMap().value("identity").toMap())==root) { events.push_back(entry); }
    }
    if (actual.sequence>=9007199254740991ULL) { actual.complete=false;return {}; }
    const auto after=clock(actual);
    QVariantMap result{{"iosWorldWebVersion",2},{"commandId",query.value("commandId")},{"runId",query.value("runId")},
        {"fixtureUrl",root},{"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},
        {"processId",QCoreApplication::applicationPid()},{"clockDomain","native-main-ios-world-web"},
        {"clockBefore",before},{"clockAfter",after},{"complete",actual.complete},
        {"eventSequence",static_cast<qulonglong>(actual.eventSequence)},{"events",events}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>1048576) { actual.complete=false;return {}; }
    return result;
}
} // namespace overte::ios::world_web_trace
Q_DECLARE_METATYPE(overte::ios::world_web_trace::Provider)
#endif
