// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSQmlSourceObservation.h"

#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(OVERTE_E2E_QML_PRIVATE_API)
#include <QtQml/private/qqmltypedata_p.h>
#endif

#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QPointer>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QThread>
#include <QUuid>
#include <atomic>

namespace {
// Allocation-free and independent of State construction. A missed second load
// must never leave the first root looking like the sole observed candidate.
std::atomic<bool> observationFailed { false };
QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
bool enabled() {
    return !observationFailed.load(std::memory_order_acquire) && QCoreApplication::instance()
        && QThread::currentThread() == QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains(QStringLiteral("--testScript"))
        && QString::fromLatin1(qVersion()) == QStringLiteral("6.11.1")
        && QQmlTypeData::overteE2eSourceObservationApiVersion() == 1;
}
bool local(const QUrl& url) {
    return (url.scheme() == "file" || url.scheme() == "qrc") && url.authority().isEmpty()
        && !url.hasQuery() && !url.hasFragment() && url.toString(QUrl::FullyEncoded).size() <= 4096;
}
QVariantMap cacheReceipt(QObject *object,QQmlComponent *component=nullptr,const void **called=nullptr) {
#if defined(QT_OVERTE_E2E_QML_CACHE_ORIGINALS)
    if (QQmlTypeData::overteE2eCacheObservationApiVersion()==1) {
        const auto actual=&QQmlTypeData::overteE2eCacheReceiptForObject;
        if (called) *called=reinterpret_cast<const void *>(actual);
        return actual(object,component);
    }
#endif
    Q_UNUSED(object);Q_UNUSED(component);Q_UNUSED(called);return {};
}
bool dependencyApiPresent() {
#if defined(QT_OVERTE_E2E_QML_DEPENDENCY_ORIGINALS)
    return true;
#else
    return false;
#endif
}
QVariantMap dependencyReceipt(QObject *object,QQmlComponent *component=nullptr,const void **called=nullptr) {
#if defined(QT_OVERTE_E2E_QML_DEPENDENCY_ORIGINALS)
    if (QQmlTypeData::overteE2eDependencyObservationApiVersion()==1) {
        const auto actual=&QQmlTypeData::overteE2eDependencyOriginalForObject;
        if (called) *called=reinterpret_cast<const void *>(actual);
        return actual(object,component);
    }
#endif
    Q_UNUSED(object);Q_UNUSED(component);Q_UNUSED(called);return {};
}
bool dependencyMatchesCache(const QVariantMap &graph,const QVariantMap &cache) {
    if (graph.isEmpty() || cache.isEmpty() || graph.value("executableUnitId")!=cache.value("executableUnitId")
            || graph.value("componentMatched")!=cache.value("componentMatched")) return false;
    const auto nodes=graph.value("source").toMap().value("afterOriginal").toMap().value("nodes").toList();
    if (nodes.isEmpty()) return false;
    const auto root=nodes.first().toMap().value("unit").toMap();const auto unit=cache.value("unit").toMap();
    if (root.value("aot").toBool()) return false;
    for (const auto &key:{"unitOwnerId","unitGeneration","unitBytes","unitSha256"})
        if (!root.contains(key) || root.value(key)!=unit.value(key)) return false;
    return true;
}
QVariantMap dependencyMembership(const QVariantMap &object) {
    auto original=object.value("source").toMap().value("afterOriginal").toMap();
    auto nodes=original.value("nodes").toList();auto edges=original.value("edges").toList();
    for (auto &value:nodes) {
        auto node=value.toMap();auto source=node.value("sourceOriginal").toMap();
        node.remove("captureBefore");node.remove("captureAfter");
        if (node.value("sourceKind").toString()==QStringLiteral("mapped-cache")) {
            source.remove("unitReadBefore");source.remove("unitReadAfter");node.insert("sourceOriginal",source);
        }
        value=node;
    }
    for (auto &value:edges) {auto edge=value.toMap();edge.remove("evaluation");value=edge;}
    original.insert("nodes",nodes);original.insert("edges",edges);return original;
}

bool sameCacheIdentity(const QVariantMap &original,const QVariantMap &current) {
    if (original.isEmpty() || current.isEmpty()) return false;
    auto a=original,b=current;
    if (!a.value("componentMatched").toBool() || b.value("componentMatched").toBool()) return false;
    a.remove("componentMatched");b.remove("componentMatched");
    auto au=a.value("unit").toMap(),bu=b.value("unit").toMap();
    for (const auto &name : {QStringLiteral("unitReadBefore"),QStringLiteral("unitReadAfter")}) {
        au.remove(name);bu.remove(name);
    }
    a.insert("unit",au);b.insert("unit",bu);return a==b;
}
struct Load {
    QString ticket, objectId, contextId, objectContextId;
    QString componentUrl, creationContextUrl, objectContextUrl;
    QPointer<QQmlComponent> component;
    QPointer<QQmlContext> context, objectContext;
    QPointer<QObject> object;
    QUrl requested, selected;
    QVariantMap before, after, source, cache;
    bool completed { false };
    const void *cacheFunction { nullptr };
    QVariantMap dependency;const void *dependencyFunction { nullptr };bool dependencyRequired{false};
};
struct State {
    State() { timer.start(); }
    QVariantMap clock() const { return {{"epochMs", QDateTime::currentMSecsSinceEpoch()}, {"monotonicMs", timer.elapsed()}}; }
    QElapsedTimer timer;
    QList<Load> loads;
    bool failed { false };
    const QString instance { nonce() };
};
State& state() { static State value; return value; }
}
#endif

namespace hifi::qml {
QString IOSQmlSourceObservation::begin(const QUrl& requested, const QUrl& selected, QQmlContext* context) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
    try {
        // Select the actual original Chat load, without changing its URLs.
        if (!enabled() || !requested.path().endsWith("/armored-chat/armored_chat.qml")) { return {}; }
        if (!local(requested) || !local(selected) || !context || context->thread() != QThread::currentThread()) {
            observationFailed.store(true, std::memory_order_release); return {};
        }
        auto& owner = state();
        if (owner.failed || owner.loads.size() >= 64) { owner.failed = true; return {}; }
        QQmlTypeData::setOverteE2eSourceObservationEnabled(true);
        Load row; row.ticket = nonce(); row.contextId = nonce(); row.context = context;
        row.requested = requested; row.selected = selected; row.before = owner.clock();
        owner.loads.append(row);
        return row.ticket;
    } catch (...) { observationFailed.store(true, std::memory_order_release); return {}; }
#else
    Q_UNUSED(requested); Q_UNUSED(selected); Q_UNUSED(context);
    return {};
#endif
}

void IOSQmlSourceObservation::attach(const QString& ticket, QQmlComponent* component) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
    try {
        if (!enabled() || ticket.isEmpty() || !component || component->thread() != QThread::currentThread()) { return; }
        auto& owner = state();
        if (owner.failed) { return; }
        for (auto& row : owner.loads) {
            if (row.ticket == ticket) {
                if (row.completed || row.component) { owner.failed = true; return; }
                row.component = component;
                return;
            }
        }
    } catch (...) {
        observationFailed.store(true, std::memory_order_release);
        // Ordinary QML loading keeps its original outcome.
    }
#else
    Q_UNUSED(ticket); Q_UNUSED(component);
#endif
}

void IOSQmlSourceObservation::complete(QQmlComponent* component, QQmlContext* context, QObject* object) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
    try {
        if (!enabled() || !component || !context || !object
                || component->thread() != QThread::currentThread() || context->thread() != QThread::currentThread()
                || object->thread() != QThread::currentThread() || !component->isReady() || component->isError()) { return; }
        auto& owner = state();
        if (owner.failed) { return; }
        for (auto& row : owner.loads) {
            if (row.component != component) { continue; }
            if (row.completed || row.context != context) { owner.failed = true; return; }
            // The patched binary checks the object's actual executable unit
            // against this exact component; a URL/hash alone cannot satisfy it.
            const auto actualContext = QQmlEngine::contextForObject(object);
            if (!actualContext || actualContext->thread() != QThread::currentThread()) { owner.failed = true; return; }
            // Retain the weak root even if its code association is unavailable;
            // a later observer must not hide an opaque second Chat page.
            row.object = object; row.objectId = nonce(); row.objectContext = actualContext;
            row.componentUrl = component->url().toString(QUrl::FullyEncoded);
            row.creationContextUrl = context->baseUrl().toString(QUrl::FullyEncoded);
            row.objectContextUrl = actualContext->baseUrl().toString(QUrl::FullyEncoded);
            row.objectContextId = nonce(); row.completed = true;
            const auto source = QQmlTypeData::overteE2eSourceReceiptForObject(object, component);
            // The version-one direct path stays unchanged. Cache observation
            // is a distinct optional version, never a guessed direct receipt.
            const void *cacheFunction=nullptr;
            const auto cache=source.isEmpty() ? cacheReceipt(object,component,&cacheFunction) : QVariantMap();
            if (source.isEmpty() && cache.isEmpty()) { return; }
            const bool dependencyRequired=source.isEmpty() && dependencyApiPresent();
            const void *dependencyFunction=nullptr;
            const auto dependency=dependencyRequired ? dependencyReceipt(object,component,&dependencyFunction) : QVariantMap();
            if (dependencyRequired && !dependencyMatchesCache(dependency,cache)) return;
            const auto after = owner.clock();
            const auto start = row.before.value("epochMs").toLongLong();
            const auto end = after.value("epochMs").toLongLong();
            const auto delta = end - start;
            const auto elapsed = after.value("monotonicMs").toLongLong() - row.before.value("monotonicMs").toLongLong();
            if (start <= 0 || delta < 0 || elapsed < 0 || qAbs(delta - elapsed) > 250) { return; }
            if (!source.isEmpty()) {
                if (source.value("sourceBeforeEpochMs").toLongLong() < start
                        || source.value("compiledEpochMs").toLongLong() > end) return;
            } else {
                const auto unit=cache.value("unit").toMap();
                if (!cache.value("componentMatched").toBool()
                        || unit.value("unitReadBefore").toMap().value("epochMs").toLongLong()<start
                        || unit.value("unitReadAfter").toMap().value("epochMs").toLongLong()>end) return;
            }
            // Compiler/write/map clocks inside cache remain their old values.
            // These are actual load-time unit reads, not a new compilation.
            row.after = after; row.source = source;row.cache=cache;row.cacheFunction=cacheFunction;
            row.dependency=dependency;row.dependencyFunction=dependencyFunction;row.dependencyRequired=dependencyRequired;
            return;
        }
    } catch (...) {
        observationFailed.store(true, std::memory_order_release);
        // Never replace the real completeCreate result.
    }
#else
    Q_UNUSED(component); Q_UNUSED(context); Q_UNUSED(object);
#endif
}

QVariantMap IOSQmlSourceObservation::read(QObject* object) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
    try {
        if (!enabled() || !object || object->thread() != QThread::currentThread()) { return {}; }
        auto& owner = state();
        if (owner.failed) { return {}; }
        for (qsizetype index = 0; index < owner.loads.size(); ++index) {
            const auto& row = owner.loads.at(index);
            if (!row.completed || !row.object || row.object != object) { continue; }
            if ((row.source.isEmpty() && row.cache.isEmpty()) || !row.context || !row.objectContext
                    || QQmlEngine::contextForObject(object) != row.objectContext
                    || row.context->baseUrl().toString(QUrl::FullyEncoded) != row.creationContextUrl
                    || row.objectContext->baseUrl().toString(QUrl::FullyEncoded) != row.objectContextUrl) { return {}; }
            QVariantMap currentCache,currentDependency;
            if (!row.source.isEmpty()) {
                if (QQmlTypeData::overteE2eSourceReceiptForObject(object)!=row.source) return {};
            } else {
                const void *currentFunction=nullptr;currentCache=cacheReceipt(object,nullptr,&currentFunction);
                if (!row.cacheFunction || currentFunction!=row.cacheFunction || !sameCacheIdentity(row.cache,currentCache)) return {};
            }
            if (row.dependencyRequired) {
                const void *function=nullptr;currentDependency=dependencyReceipt(object,nullptr,&function);
                if (!row.dependencyFunction || function!=row.dependencyFunction
                        || !dependencyMatchesCache(currentDependency,currentCache)
                        || dependencyMembership(row.dependency)!=dependencyMembership(currentDependency)) return {};
            }
            QVariantMap result {{"iosLoadedQmlSourceVersion", row.cache.isEmpty()?1:row.dependencyRequired?3:2}, {"instance", owner.instance},
                {"loadSequence", qlonglong(index + 1)}, {"loadId", row.ticket},
                {"objectId", row.objectId}, {"creationContextId", row.contextId}, {"objectContextId", row.objectContextId},
                {"processId", QCoreApplication::applicationPid()}, {"clockDomain", "native-main-qml-load"},
                {"loadBefore", row.before}, {"loadCompleted", row.after},
                {"requestedUrl", row.requested.toString(QUrl::FullyEncoded)},
                {"selectedUrl", row.selected.toString(QUrl::FullyEncoded)},
                {"componentUrl", row.componentUrl},
                {"creationContextUrl", row.creationContextUrl},
                {"objectContextUrl", row.objectContextUrl},
                {"compilerInput", row.source}};
            if (!row.cache.isEmpty()) {
                result.remove("compilerInput");result.insert("sourceKind","observed-cache");
                result.insert("cacheAtLoad",row.cache);result.insert("cacheAtRead",currentCache);
                result.insert("coverage",QVariantMap{{"importGraphAvailable",false},
                    {"aotGraphAvailable",false},{"installedQtSourceAvailable",false}});
            }
            if (row.dependencyRequired) {
                result.insert("dependencyAtLoad",row.dependency);result.insert("dependencyAtRead",currentDependency);
            }
            if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size() > (row.dependencyRequired?57344:32768)) { return {}; }
            return result;
        }
    } catch (...) { observationFailed.store(true, std::memory_order_release); return {}; }
#else
    Q_UNUSED(object);
#endif
    return {};
}

const void* IOSQmlSourceObservation::cacheObservationSymbol(QObject* object) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_CACHE_ORIGINALS)
    try {
        if (!enabled() || !object || object->thread()!=QThread::currentThread()) return nullptr;
        const auto current=reinterpret_cast<const void *>(&QQmlTypeData::overteE2eCacheReceiptForObject);
        for (const auto &row:state().loads)
            if (row.completed && row.object==object && !row.cache.isEmpty() && row.cacheFunction==current) return current;
    } catch (...) { observationFailed.store(true); }
#else
    Q_UNUSED(object);
#endif
    return nullptr;
}

const void* IOSQmlSourceObservation::dependencyObservationSymbol(QObject* object) noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_DEPENDENCY_ORIGINALS)
    try {
        if (!enabled() || !object || object->thread()!=QThread::currentThread()) return nullptr;
        const auto actual=reinterpret_cast<const void *>(&QQmlTypeData::overteE2eDependencyOriginalForObject);
        for (const auto &row:state().loads)
            if (row.completed && row.object==object && row.dependencyRequired && !row.dependency.isEmpty()
                    && row.dependencyFunction==actual) return actual;
    } catch (...) { observationFailed.store(true); }
#else
    Q_UNUSED(object);
#endif
    return nullptr;
}

QList<QObject*> IOSQmlSourceObservation::liveObjects() noexcept {
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(QT_OVERTE_E2E_QML_SOURCE_RECEIPTS)
    try {
        if (!enabled()) { return {}; }
        const auto& owner = state();
        if (owner.failed) { return {}; }
        QList<QObject*> result;
        for (const auto& row : owner.loads) {
            if (row.completed && row.object) { result.append(row.object.data()); }
        }
        return result;
    } catch (...) { observationFailed.store(true, std::memory_order_release); return {}; }
#endif
    return {};
}
}
