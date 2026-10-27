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
struct Load {
    QString ticket, objectId, contextId, objectContextId;
    QString componentUrl, creationContextUrl, objectContextUrl;
    QPointer<QQmlComponent> component;
    QPointer<QQmlContext> context, objectContext;
    QPointer<QObject> object;
    QUrl requested, selected;
    QVariantMap before, after, source;
    bool completed { false };
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
            if (source.isEmpty()) { return; }
            const auto after = owner.clock();
            const auto start = row.before.value("epochMs").toLongLong();
            const auto end = after.value("epochMs").toLongLong();
            const auto delta = end - start;
            const auto elapsed = after.value("monotonicMs").toLongLong() - row.before.value("monotonicMs").toLongLong();
            if (start <= 0 || delta < 0 || elapsed < 0 || qAbs(delta - elapsed) > 250
                    || source.value("sourceBeforeEpochMs").toLongLong() < start
                    || source.value("compiledEpochMs").toLongLong() > end) { return; }
            row.after = after; row.source = source;
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
            if (row.source.isEmpty() || !row.context || !row.objectContext || QQmlEngine::contextForObject(object) != row.objectContext
                    || row.context->baseUrl().toString(QUrl::FullyEncoded) != row.creationContextUrl
                    || row.objectContext->baseUrl().toString(QUrl::FullyEncoded) != row.objectContextUrl
                    || QQmlTypeData::overteE2eSourceReceiptForObject(object) != row.source) { return {}; }
            QVariantMap result {{"iosLoadedQmlSourceVersion", 1}, {"instance", owner.instance},
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
            if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size() > 32768) { return {}; }
            return result;
        }
    } catch (...) { observationFailed.store(true, std::memory_order_release); return {}; }
#else
    Q_UNUSED(object);
#endif
    return {};
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
