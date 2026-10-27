// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSAssetsImageReaderQueueObservation.h"
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#if defined(OVERTE_E2E_METACALL_PRIVATE_API)
#include <QtCore/private/qobject_p.h>
#endif
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMetaMethod>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <atomic>
#include <exception>
#include <memory>

namespace overte::e2e {
namespace {
using Observation = IOSAssetsImageReaderQueueObservation;
std::atomic<bool> observationFailed { false };
std::atomic<bool> observationArmed { false };
static_assert(std::atomic<bool>::is_always_lock_free);
void fail() noexcept { observationFailed.store(true, std::memory_order_release); }
bool gate() {
    auto *app = QCoreApplication::instance();
    return app && app->arguments().contains(QStringLiteral("--testScript"))
        && QString::fromLatin1(qVersion()) == QStringLiteral("6.11.1");
}
bool mainThread() noexcept {
    auto *app = QCoreApplication::instance();
    return app && QThread::currentThread() == app->thread();
}
QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
bool identity(const QString &value) {
    if (value.size() != 32) { return false; }
    for (const auto ch : value) {
        if (!((ch >= QLatin1Char('0') && ch <= QLatin1Char('9'))
                || (ch >= QLatin1Char('a') && ch <= QLatin1Char('f')))) { return false; }
    }
    return true;
}
bool words(const QString &value, quint64 &high, quint64 &low) {
    if (!identity(value)) { return false; }
    bool first = false, second = false;
    high = value.left(16).toULongLong(&first, 16);
    low = value.mid(16).toULongLong(&second, 16);
    return first && second && (high || low);
}
struct Entry {
    Observation::Context context;
    quint64 high { 0 }, low { 0 }, eventId { 0 };
    int methodIndex { -1 };
    QVariantMap value;
};
struct State {
    State() { timer.start(); }
    QVariantMap clock() const {
        return {{"epochMs", QDateTime::currentMSecsSinceEpoch()}, {"monotonicMs", timer.elapsed()}};
    }
    QMutex mutex;
    QElapsedTimer timer;
    QString instance { nonce() }, source1Instance;
    QVector<Entry> entries;
};
using Pin = std::shared_ptr<State>;
// Only this tiny diagnostic publication slot lasts for the process. Actual
// State is released after disarm AND its last callback/snapshot pin, outside locks.
// A late Qt callback can safely load this still-valid slot and observe null.
Pin *publication() { static Pin *const value = new Pin; return value; }
Pin acquire() { return std::atomic_load_explicit(publication(), std::memory_order_acquire); }
bool admitted() noexcept {
    return observationArmed.load(std::memory_order_acquire)
        && !observationFailed.load(std::memory_order_acquire);
}

#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
static_assert(QT_OVERTE_E2E_METACALL_RECEIPTS == 1);
bool qtHealthy() noexcept {
    return QObjectPrivate::overteE2eMetaCallApiVersion() == 1
        && QObjectPrivate::overteE2eMetaCallObservationAvailable();
}
QVariantMap qtClock(const QOverteE2eMetaCallReceipt &record) {
    // Keep the original Qt clock domain; do not retime into State::timer.
    return {{"epochMs", record.epochMs}, {"steadyNs", QString::number(record.steadyNs)}};
}
bool callback(const QOverteE2eMetaCallReceipt &record) noexcept {
    try {
        // Pin before touching State or waiting for its mutex. Disarm never waits.
        auto owner = acquire();
        if (!owner || !admitted() || !record.eventId || record.eventId > 256) { fail(); return false; }
        QMutexLocker lock(&owner->mutex);
        if (!admitted()) { return false; }
        Entry *selected = nullptr;
        for (auto &entry : owner->entries) {
            if (entry.high == record.invocationHigh && entry.low == record.invocationLow) {
                if (selected) { fail(); return false; }
                selected = &entry;
            }
        }
        if (!selected || selected->methodIndex != record.methodIndex) { fail(); return false; }
        auto &entry = *selected;
        auto &value = entry.value;
        const char *field = nullptr;
        switch (record.phase) {
        case QOverteE2eMetaCallReceipt::Created:
            if (entry.eventId || entry.context.receiver.isNull()
                    || entry.context.receiver.data() != record.receiver) { fail(); return false; }
            for (const auto &other : owner->entries) {
                if (other.eventId == record.eventId) { fail(); return false; }
            }
            entry.eventId = record.eventId;
            value["eventId"] = qulonglong(record.eventId);
            field = "created";
            break;
        case QOverteE2eMetaCallReceipt::DeliveryEntered:
            if (value.value("created").isNull() || !value.value("argumentValuesDestroyed").isNull()
                    || entry.context.receiver.isNull()
                    || entry.context.receiver.data() != record.receiver) { fail(); return false; }
            field = "deliveryEntered";
            break;
        case QOverteE2eMetaCallReceipt::DeliveryReturned:
        case QOverteE2eMetaCallReceipt::DeliveryUnwound:
            if (value.value("deliveryEntered").isNull()
                    || !value.value("deliveryReturned").isNull()
                    || !value.value("deliveryUnwound").isNull()
                    || entry.context.receiver.isNull()
                    || entry.context.receiver.data() != record.receiver) { fail(); return false; }
            field = record.phase == QOverteE2eMetaCallReceipt::DeliveryReturned
                ? "deliveryReturned" : "deliveryUnwound";
            break;
        case QOverteE2eMetaCallReceipt::ArgumentValuesDestroyed:
            if (value.value("created").isNull() || record.receiver
                    || (!value.value("deliveryEntered").isNull()
                        && value.value("deliveryReturned").isNull()
                        && value.value("deliveryUnwound").isNull())) { fail(); return false; }
            field = "argumentValuesDestroyed";
            break;
        default: fail(); return false;
        }
        if (entry.eventId != record.eventId || !value.value(field).isNull()) { fail(); return false; }
        value[field] = qtClock(record);
        return admitted();
    } catch (...) { fail(); return false; }
}
#else
bool qtHealthy() noexcept { return false; }
#endif
}

void Observation::prepare() noexcept {
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
    try {
        if (observationFailed.load(std::memory_order_acquire)) { return; }
        if (!gate() || !mainThread() || QObjectPrivate::overteE2eMetaCallApiVersion() != 1) { fail(); return; }
        if (observationArmed.load(std::memory_order_acquire)) {
            if (!qtHealthy()) { fail(); }
            return;
        }
        auto owner = std::make_shared<State>();
        // Install the shutdown hook before admission; it captures no State/product owner.
        auto *app = QCoreApplication::instance();
        const auto connection = QObject::connect(app, &QCoreApplication::aboutToQuit,
            app, [] { Observation::disarm(); }, Qt::DirectConnection);
        const auto destroyed = QObject::connect(app, &QObject::destroyed,
            app, [] { Observation::disarm(); }, Qt::DirectConnection);
        if (!connection || !destroyed) { fail(); return; }
        std::atomic_store_explicit(publication(), owner, std::memory_order_release);
        observationArmed.store(true, std::memory_order_release);
        // No Bridge/Source1 mutex is held across any Qt diagnostic API call.
        QObjectPrivate::setOverteE2eMetaCallObserver(&callback, true);
        if (!qtHealthy()) { disarm(); }
    } catch (...) { fail(); disarm(); }
#else
    fail();
#endif
}

void Observation::disarm() noexcept {
    // A running callback owns its independent State pin before it can wait on mutex.
    // Clearing publication blocks new pins; no waiting drain or State lock is needed.
    fail();
    observationArmed.store(false, std::memory_order_release);
    try {
        auto retired = std::atomic_exchange_explicit(publication(), Pin {}, std::memory_order_acq_rel);
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
        QObjectPrivate::setOverteE2eMetaCallObserver(&callback, false);
#endif
        // retired releases outside every registry mutex. Other callbacks retain theirs.
    } catch (...) { fail(); }
}

void Observation::Binding::begin(const Context &context, QObject *receiver) noexcept {
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
    try {
        if (_row || _qtScope || !gate() || !admitted() || !qtHealthy()) { fail(); return; }
        quint64 high = 0, low = 0;
        if (!identity(context.ownerInstance) || !identity(context.taskId)
                || !identity(context.resourceId) || !context.receiverId.isEmpty()
                || !words(context.dispatchId, high, low) || !receiver
                || context.receiver.isNull() || context.receiver.data() != receiver) { fail(); return; }
        // Read actual metadata before the registry lock. Unknown signature stays unavailable.
        const int methodIndex = receiver->metaObject()->indexOfMethod("setImage(gpu::TexturePointer,int,int)");
        if (methodIndex < 0) { fail(); return; }
        auto owner = acquire();
        if (!owner) { fail(); return; }
        {
            QMutexLocker lock(&owner->mutex);
            if (!admitted() || owner->entries.size() >= 256
                    || (!owner->source1Instance.isEmpty() && owner->source1Instance != context.ownerInstance)) { fail(); return; }
            for (const auto &other : owner->entries) {
                if (other.high == high && other.low == low) { fail(); return; }
            }
            Entry entry; entry.context = context; entry.high = high; entry.low = low; entry.methodIndex = methodIndex;
            entry.value = {{"dispatchId", context.dispatchId}, {"taskId", context.taskId},
                {"resourceId", context.resourceId}, {"methodIndex", methodIndex},
                {"bindingEntered", owner->clock()}, {"invokeReturned", QVariant()},
                {"invokeAccepted", QVariant()}, {"eventId", QVariant()},
                {"created", QVariant()}, {"deliveryEntered", QVariant()},
                {"deliveryReturned", QVariant()}, {"deliveryUnwound", QVariant()},
                {"argumentValuesDestroyed", QVariant()}, {"receiverId", QVariant()},
                {"receiverEntered", QVariant()}, {"receiverReturned", QVariant()}, {"receiverUnwound", QVariant()}};
            owner->source1Instance = context.ownerInstance;
            owner->entries.append(entry); _row = quint64(owner->entries.size());
        }
        _qtScope = QObjectPrivate::beginOverteE2eMetaCallBinding(receiver, methodIndex, high, low);
        if (!_qtScope) { fail(); }
    } catch (...) { fail(); }
#else
    Q_UNUSED(context); Q_UNUSED(receiver); fail();
#endif
}

void Observation::Binding::returned(bool accepted) noexcept {
    _returned = true;
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
    // Closing the actual thread-local Qt scope happens outside every app mutex.
    const auto id = QObjectPrivate::endOverteE2eMetaCallBinding(_qtScope); _qtScope = 0;
    try {
        auto owner = acquire();
        if (!owner || !_row || !admitted() || !qtHealthy()) { fail(); return; }
        QMutexLocker lock(&owner->mutex);
        if (_row > quint64(owner->entries.size()) || !admitted()) { fail(); return; }
        auto &entry = owner->entries[int(_row - 1)];
        if (!entry.value.value("invokeReturned").isNull() || id != entry.eventId
                || (id && !accepted)) { fail(); return; }
        entry.value["invokeReturned"] = owner->clock(); entry.value["invokeAccepted"] = accepted;
    } catch (...) { fail(); }
#else
    Q_UNUSED(accepted);
#endif
}

Observation::Binding::~Binding() noexcept {
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
    if (_qtScope) {
        // Preserve the product exception; diagnostics do not throw or wait.
        fail(); QObjectPrivate::endOverteE2eMetaCallBinding(_qtScope);
    }
#endif
    if (_row && !_returned) { fail(); }
}

void Observation::Receiver::begin(const Context &context) noexcept {
#if defined(QT_OVERTE_E2E_METACALL_RECEIPTS)
    try {
        if (!gate() || !admitted() || !qtHealthy()) { return; }
        if (!identity(context.ownerInstance) || !identity(context.resourceId)
                || !identity(context.receiverId) || context.receiver.isNull()) { fail(); return; }
        const auto id = QObjectPrivate::currentOverteE2eMetaCallEvent(context.receiver.data());
        if (!id) { return; } // An unobserved/direct producer gains no guessed association.
        auto owner = acquire();
        if (!owner) { fail(); return; }
        QMutexLocker lock(&owner->mutex);
        if (!admitted() || owner->source1Instance != context.ownerInstance) { fail(); return; }
        for (int index = 0; index < owner->entries.size(); ++index) {
            auto &entry = owner->entries[index];
            if (entry.eventId != id) { continue; }
            if (entry.context.receiver.isNull() || entry.context.receiver != context.receiver
                    || entry.context.resourceId != context.resourceId
                    || entry.value.value("deliveryEntered").isNull()
                    || !entry.value.value("receiverId").isNull()) { fail(); return; }
            entry.value["receiverId"] = context.receiverId;
            entry.value["receiverEntered"] = owner->clock();
            _row = quint64(index + 1); _exceptions = std::uncaught_exceptions(); return;
        }
        fail();
    } catch (...) { fail(); }
#else
    Q_UNUSED(context);
#endif
}

Observation::Receiver::~Receiver() noexcept {
    if (!_row) { return; }
    try {
        auto owner = acquire();
        if (!owner || !admitted()) { fail(); return; }
        QMutexLocker lock(&owner->mutex);
        if (_row > quint64(owner->entries.size()) || !admitted()) { fail(); return; }
        auto &value = owner->entries[int(_row - 1)].value;
        if (!value.value("receiverReturned").isNull() || !value.value("receiverUnwound").isNull()) { fail(); return; }
        value[std::uncaught_exceptions() > _exceptions ? "receiverUnwound" : "receiverReturned"] = owner->clock();
    } catch (...) { fail(); }
}

QVariantMap Observation::snapshot() noexcept {
    try {
        if (!gate() || !mainThread() || !admitted() || !qtHealthy()) { return {}; }
        auto owner = acquire();
        if (!owner) { return {}; }
        QVariantMap result;
        {
            // Admission alone is not an actual observed Source1 parent.
            // Before the first native Dispatch context, this source is unavailable.
            QMutexLocker lock(&owner->mutex);
            if (owner->source1Instance.isEmpty()) { return {}; }
            QVariantList entries;
            for (const auto &entry : owner->entries) {
                auto value = entry.value; value["receiverObjectAlive"] = !entry.context.receiver.isNull();
                entries.append(value);
            }
            result = {{"assetImageReaderQueueHistoryVersion", 1}, {"instance", owner->instance},
                {"source1Instance", owner->source1Instance}, {"complete", admitted()},
                {"clockDomain", "native-assets-image-reader-queue-observer"}, {"clock", owner->clock()},
                {"qtClockDomain", "qtcore-metacall-steady-nanoseconds"}, {"entries", entries},
                {"eventStorageCompletionAvailable", false}, {"byteCopyCompletionAvailable", false},
                {"basePoolCompletionAvailable", false}, {"decoderCompletionAvailable", false},
                {"gpuCompletionAvailable", false}, {"resourceRetirementAvailable", false}};
        }
        // Disarm/failure racing a snapshot cannot return a former complete result.
        if (!admitted() || !qtHealthy()) { return {}; }
        return result;
    } catch (...) { fail(); return {}; }
}
}
#endif
