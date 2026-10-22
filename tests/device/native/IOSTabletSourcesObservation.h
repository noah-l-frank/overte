// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <InlineHtmlDocument.h>
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QList>
#include <QPointer>
#include <QQuickItem>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QVariant>
#include <memory>

namespace overte::e2e::tablet_sources {
inline QString id() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
inline bool enabled() {
    if (!QCoreApplication::instance()) { return false; }
    const auto args=QCoreApplication::arguments();const auto a=args.indexOf("--testScript"),b=args.indexOf("--testResultsLocation");
    return a>=0 && a+1<args.size() && !args[a+1].isEmpty() && b>=0 && b+1<args.size() && !args[b+1].isEmpty();
}
inline bool mainThread() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread(); }
inline QString sha(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
inline QString fixtureRoot(const QString& raw) {
    const QUrl url(raw,QUrl::StrictMode);const auto found=QRegularExpression("\\A(/feature-fixture/v1/runs/[0-9a-f]{32}/)tickets/[0-9a-f]{32}/(?:index|reference)\\.html\\z").match(url.path());
    if (!url.isValid() || !found.hasMatch() || (url.scheme()!="http" && url.scheme()!="https") || url.host().isEmpty()
            || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || url.toString(QUrl::FullyEncoded)!=raw) { return {}; }
    auto root=url;root.setPath(found.captured(1));return root.toString(QUrl::FullyEncoded);
}
inline bool command(const QVariantMap& value) {
    const auto object=QJsonObject::fromVariantMap(value);const auto keys=object.keys();const auto root=object.value("fixtureUrl").toString(),run=object.value("runId").toString();
    const QUrl url(root,QUrl::StrictMode);
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl"}
        && object.value("schemaVersion")==QJsonValue(1) && object.value("action")==QJsonValue("feature-ios-tablet-sources")
        && QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(object.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() && root.size()<=512
        && !root.contains(QRegularExpression("[\\x00-\\x20\\x7f]")) && url.isValid() && (url.scheme()=="http" || url.scheme()=="https")
        && !url.host().isEmpty() && url.userInfo().isEmpty() && !url.hasQuery() && !url.hasFragment()
        && url.path()=="/feature-fixture/v1/runs/"+run+"/" && url.toString(QUrl::FullyEncoded)==root;
}
struct Root { QString birth;QPointer<QQuickItem> item;QString current,fixture;QVariantMap original; };
struct Navigation { QString birth,root,fixture,url,script;QVariantMap original; };
struct Binding { QString birth;QPointer<QObject> context;QPointer<QQuickItem> page;web::InlineHtmlDocument document;QVariantMap original; };
struct Carrier { QString birth,navigation,root,identity;QPointer<QObject> owner;QVariantMap original;QList<std::shared_ptr<Binding>> bindings; };
struct State {
    QMutex mutex;const QString instance{id()};QElapsedTimer timer;quint64 sequence{0};qint64 epoch{0},mono{0};bool complete{true};
    QList<std::shared_ptr<Root>> roots;QList<std::shared_ptr<Navigation>> navigations;QList<std::shared_ptr<Carrier>> carriers;
    State() { timer.start(); }
};
inline State& state() { static State actual;return actual; }
inline QVariantMap clock(State& actual) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.epoch || mono<actual.mono || (actual.epoch && qAbs(epoch-actual.epoch-mono+actual.mono)>250)) { actual.complete=false; }
    actual.epoch=epoch;actual.mono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline std::shared_ptr<Root> findRoot(State& actual,QQuickItem* item) {
    for (const auto& row:actual.roots) { if (row->item==item) { return row; } }return {};
}
inline std::shared_ptr<Navigation> findNavigation(State& actual,const QString& birth) {
    for (const auto& row:actual.navigations) { if (row->birth==birth) { return row; } }return {};
}
inline std::shared_ptr<Carrier> findCarrier(State& actual,QObject* owner) {
    for (const auto& row:actual.carriers) { if (row->owner==owner) { return row; } }return {};
}
// Called from the actual native source-navigation entry, before its unchanged
// QML invocation. This records an input; it never claims a loaded document.
inline QString navigation(QQuickItem* item,const QString& tablet,const QString& source,const QString& script) {
    if (!enabled() || !mainThread() || !item || item->thread()!=QThread::currentThread()) { return {}; }
    auto& actual=state();QMutexLocker guard(&actual.mutex);auto root=findRoot(actual,item);auto fixture=fixtureRoot(source);
    web::InlineHtmlBytes decoded;
    if (source.startsWith("data:",Qt::CaseInsensitive)) {
        if (!root || root->fixture.isEmpty()) { return {}; }decoded=web::InlineHtmlBytes::decode(source);
        if (!decoded.valid() || decoded.body.size()>262144) { actual.complete=false;return {}; }
        const auto run=QUrl(root->fixture).path().section('/',4,4);
        const auto marker=QByteArray("<meta name=\"overte-fixture-owner\" content=\"")+run.toUtf8()+"\">";
        if (decoded.body.count(marker)!=1) { return {}; }fixture=root->fixture;
    }
    if (fixture.isEmpty()) { if (root) { root->current.clear();root->fixture.clear(); }return {}; }
    if (source.toUtf8().size()>1048576 || script.toUtf8().size()>4096 || tablet.toUtf8().size()>512 || actual.navigations.size()>=128) { actual.complete=false;return {}; }
    if (!root) {
        if (actual.roots.size()>=32) { actual.complete=false;return {}; }root=std::make_shared<Root>();root->birth=id();root->item=item;
        root->original={{"id",root->birth},{"clock",clock(actual)}};actual.roots.push_back(root);
        const auto birth=root->birth;QObject::connect(item,&QObject::destroyed,QCoreApplication::instance(),[birth] {
            auto& s=state();QMutexLocker locked(&s.mutex);if (!mainThread()) { s.complete=false;return; }
            for (const auto& r:s.roots) { if (r->birth==birth) { r->original.insert("destroyed",clock(s));return; } }
        },Qt::DirectConnection);
    }
    auto row=std::make_shared<Navigation>();row->birth=id();row->root=root->birth;row->fixture=fixture;row->url=source;row->script=script;
    QVariant body;
    if (decoded.valid()) { body=QVariantMap{{"base64",QString::fromLatin1(decoded.body.toBase64())},{"sha256",sha(decoded.body)},{"charset",decoded.charset}}; }
    row->original={{"id",row->birth},{"root",root->birth},{"fixtureUrl",fixture},{"tablet",tablet},{"sourceUrl",source},
        {"sourceSha256",sha(source.toUtf8())},{"scriptUrl",script},{"kind",decoded.valid()?"inline":"http"},{"body",body},{"clock",clock(actual)}};
    actual.navigations.push_back(row);root->current=row->birth;root->fixture=fixture;return row->birth;
}
inline void returned(const QString& birth,bool loaded) {
    if (birth.isEmpty() || !enabled()) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);
    if (!mainThread()) { actual.complete=false;return; }auto row=findNavigation(actual,birth);
    if (!row || row->original.contains("returned")) { actual.complete=false;return; }
    row->original.insert("returned",QVariantMap{{"clock",clock(actual)},{"invoked",loaded}});
}
inline void born(QObject* owner,QQuickItem* item,const QString& identity,const QString& source,const QString& script) {
    if (!enabled() || !mainThread() || !owner || !item) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);auto root=findRoot(actual,item);
    if (!root || root->current.isEmpty()) { return; }auto nav=findNavigation(actual,root->current);
    if (!nav || nav->url!=source || nav->script!=script || nav->original.value("kind")!="inline") { return; }
    if (actual.carriers.size()>=128 || findCarrier(actual,owner)) { actual.complete=false;return; }
    auto row=std::make_shared<Carrier>();row->birth=id();row->navigation=nav->birth;row->root=root->birth;row->identity=identity;row->owner=owner;
    row->original={{"id",row->birth},{"navigation",nav->birth},{"root",root->birth},{"identity",identity},{"clock",clock(actual)}};actual.carriers.push_back(row);
    const auto birth=row->birth;QObject::connect(owner,&QObject::destroyed,QCoreApplication::instance(),[birth] {
        auto& s=state();QMutexLocker locked(&s.mutex);if (!mainThread()) { s.complete=false;return; }
        for (const auto& r:s.carriers) { if (r->birth==birth) { r->original.insert("destroyed",clock(s));return; } }
    },Qt::DirectConnection);
}
inline void bound(QObject* owner,QQuickItem* page,const web::InlineHtmlDocument& document) {
    if (!enabled() || !mainThread() || !document.current()) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);auto row=findCarrier(actual,owner);if (!row) { return; }
    const auto nav=findNavigation(actual,row->navigation);
    if (!nav || !page || !document.context() || document.scriptURL()!=nav->script
            || !document.currentFor(document.context(),row->identity,nav->url)) { actual.complete=false;return; }
    for (const auto& binding:row->bindings) { if (binding->original.value("token").toString()==document.token()) { return; } }
    if (row->bindings.size()>=128) { actual.complete=false;return; }
    auto item=std::make_shared<Binding>();item->birth=id();item->context=document.context();item->page=page;item->document=document;
    item->original={{"id",item->birth},{"clock",clock(actual)},{"token",document.token()},
        {"revision",static_cast<qulonglong>(document.revision())},{"transportUrl",document.transportURL().toString(QUrl::FullyEncoded)},
        {"sha256",QString::fromLatin1(document.sha256().toHex())},{"charset",document.charset()}};row->bindings.push_back(item);
    const auto carrier=row->birth,birth=item->birth;document.onRevoked(QCoreApplication::instance(),[carrier,birth] {
        auto& s=state();QMutexLocker locked(&s.mutex);if (!mainThread()) { s.complete=false;return; }
        for (const auto& r:s.carriers) { if (r->birth==carrier) { for (const auto& b:r->bindings) { if (b->birth==birth) { b->original.insert("revoked",clock(s));return; } } } }
    },Qt::DirectConnection);
}
inline void bindReturned(QObject* owner,const QString& token) {
    if (!enabled() || !mainThread()) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);auto row=findCarrier(actual,owner);if (!row) { return; }
    for (const auto& binding:row->bindings) {
        if (binding->original.value("token").toString()==token) {
            if (binding->original.contains("returned")) { actual.complete=false;return; }
            binding->original.insert("returned",clock(actual));return;
        }
    }
    actual.complete=false;
}
inline void retiring(QObject* owner) {
    if (!enabled() || !mainThread()) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);auto row=findCarrier(actual,owner);
    if (row && !row->original.contains("retired")) { row->original.insert("retired",clock(actual)); }
}
inline void retireReturned(QObject* owner) {
    if (!enabled() || !mainThread()) { return; }auto& actual=state();QMutexLocker guard(&actual.mutex);auto row=findCarrier(actual,owner);
    if (row && row->original.contains("retired") && !row->original.contains("retireReturned")) { row->original.insert("retireReturned",clock(actual)); }
}
// Association is read from actual visual ancestry and the original native
// navigation; a command/DOM label cannot attach an arbitrary native view.
inline QVariantMap view(QQuickItem* consumer,const QString& source,const QString& identity,const web::InlineHtmlDocument& document={}) {
    if (!enabled() || !mainThread() || !consumer) { return {}; }auto& actual=state();QMutexLocker guard(&actual.mutex);
    std::shared_ptr<Root> root;
    for (auto* item=consumer;item;item=item->parentItem()) {
        root=findRoot(actual,item);if (root) { break; }
    }
    if (!root || root->current.isEmpty()) { return {}; }const auto nav=findNavigation(actual,root->current);
    if (!nav || nav->url!=source || !nav->original.contains("returned")
            || nav->original.value("returned").toMap().value("invoked")!=QVariant(true)) { return {}; }
    QVariantMap result{{"root",root->birth},{"navigation",nav->birth},{"fixtureUrl",nav->fixture}};
    if (nav->original.value("kind")=="http") {
        if (document.current()) { return {}; }result.insert("carrier",QVariant());result.insert("binding",QVariant());return result;
    }
    if (!document.currentFor(document.context(),identity,source)) { return {}; }
    for (const auto& carrier:actual.carriers) {
        if (carrier->navigation!=nav->birth || carrier->root!=root->birth || carrier->identity!=identity || carrier->owner.isNull()) { continue; }
        for (const auto& binding:carrier->bindings) {
            if (binding->document.current() && binding->original.value("token")==document.token()
                    && binding->page && (binding->page==consumer || binding->page->isAncestorOf(consumer))) {
                result.insert("carrier",carrier->birth);result.insert("binding",binding->birth);return result;
            }
        }
    }
    return {};
}
inline QVariantMap observe(const QVariantMap& query) {
    if (!enabled() || !mainThread() || !command(query)) { return {}; }auto& actual=state();QMutexLocker guard(&actual.mutex);
    const auto before=clock(actual);const auto fixture=query.value("fixtureUrl").toString();QVariantList roots,navigations,carriers;QSet<QString> rootIds,navIds;
    for (const auto& nav:actual.navigations) { if (nav->fixture==fixture) { navigations.push_back(nav->original);rootIds.insert(nav->root);navIds.insert(nav->birth); } }
    for (const auto& root:actual.roots) { if (rootIds.contains(root->birth)) { auto row=root->original;row.insert("alive",!root->item.isNull());roots.push_back(row); } }
    for (const auto& carrier:actual.carriers) {
        if (!navIds.contains(carrier->navigation)) { continue; }auto row=carrier->original;row.insert("alive",!carrier->owner.isNull());QVariantList bindings;
        for (const auto& binding:carrier->bindings) {
            auto observed=binding->original;observed.insert("current",binding->document.current());observed.insert("contextAlive",!binding->context.isNull());
            observed.insert("pageAlive",!binding->page.isNull());bindings.push_back(observed);
        }
        row.insert("bindings",bindings);carriers.push_back(row);
    }
    if (actual.sequence>=9007199254740991ULL) { actual.complete=false;return {}; }
    const auto after=clock(actual);QVariantMap result{{"iosTabletSourcesVersion",1},{"commandId",query.value("commandId")},{"runId",query.value("runId")},
        {"fixtureUrl",fixture},{"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-main-ios-tablet-sources"},{"clockBefore",before},{"clockAfter",after},{"complete",actual.complete},
        {"roots",roots},{"navigations",navigations},{"carriers",carriers}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>2097152) { actual.complete=false;return {}; }
    return result;
}
} // namespace overte::e2e::tablet_sources
#endif
