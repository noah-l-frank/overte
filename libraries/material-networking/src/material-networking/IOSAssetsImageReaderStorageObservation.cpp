// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSAssetsImageReaderStorageObservation.h"
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <atomic>

namespace overte::e2e {
namespace {
using Observation=IOSAssetsImageReaderStorageObservation;
std::atomic<bool> failed{false},armed{false};
static_assert(std::atomic<bool>::is_always_lock_free);
void fail() noexcept {failed.store(true,std::memory_order_release);}
bool admitted() noexcept {return armed.load(std::memory_order_acquire) && !failed.load(std::memory_order_acquire);}
thread_local bool observing=false;
struct Callback {
    bool entered{false};
    Callback() noexcept {if (observing) {fail();}else {observing=true;entered=true;}}
    ~Callback() {if (entered) {observing=false;}}
};
bool mainThread() noexcept {auto* app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread();}
bool gate() {auto* app=QCoreApplication::instance();return app && mainThread()
    && app->arguments().contains(QStringLiteral("--testScript")) && QString::fromLatin1(qVersion())==QStringLiteral("6.11.1");}
QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
bool identity(const QString& id) {
    if (id.size()!=32) {return false;}
    for (const auto ch:id) {if (!((ch>='0' && ch<='9') || (ch>='a' && ch<='f'))) {return false;}}
    return true;
}
thread_local QString actualThreadContext;
QString threadContext() {if (actualThreadContext.isEmpty()) {actualThreadContext=nonce();}return actualThreadContext;}
struct Row {QVariantMap value;std::weak_ptr<void> marker;};
struct State {
    State() {timer.start();}
    QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",timer.elapsed()}};}
    QVariantMap phase() const {auto result=clock();result["threadContextId"]=threadContext();return result;}
    QMutex mutex;QElapsedTimer timer;QString instance{nonce()},source1Instance;QVector<Row> rows;
    // Only currently allocated generations live here. Remove BEFORE free;
    // an address recycled before old return publication gets a new row.
    QHash<void*,quint64> addresses;
};
using Pin=std::shared_ptr<State>;
Pin* publication() {static Pin* const slot=new Pin;return slot;}
Pin acquire() {return std::atomic_load_explicit(publication(),std::memory_order_acquire);}
void setPhase(const Pin& owner,quint64 index,const char* name,const QVariantMap& original) {
    QMutexLocker lock(&owner->mutex);
    if (!admitted()) {return;}
    if (!index || index>quint64(owner->rows.size())) {fail();return;}
    auto& row=owner->rows[int(index-1)].value;
    if (!row.value(name).isNull()) {fail();return;}
    row[name]=original;
}
} // namespace

Observation::Token Observation::allocationEntering(std::size_t bytes) noexcept {
    Callback callback;if (!callback.entered) {return {};}
    Token result;
    try {
        if (!gate() || failed.load(std::memory_order_acquire)) {return result;}
        if (!bytes || bytes>1048576) {fail();return result;}
        auto owner=acquire();
        if (!owner) {
            owner=std::make_shared<State>();auto* app=QCoreApplication::instance();
            const auto quit=QObject::connect(app,&QCoreApplication::aboutToQuit,app,[] {Observation::disarm();},Qt::DirectConnection);
            const auto destroyed=QObject::connect(app,&QObject::destroyed,app,[] {Observation::disarm();},Qt::DirectConnection);
            if (!quit || !destroyed) {fail();return result;}
            std::atomic_store_explicit(publication(),owner,std::memory_order_release);armed.store(true,std::memory_order_release);
        }
        const auto original=owner->phase();const auto generation=nonce();
        QMutexLocker lock(&owner->mutex);
        if (!admitted() || owner->rows.size()>=64) {fail();return result;}
        Row row;row.value={{"id",generation},{"storageBytes",qulonglong(bytes)},
            {"taskId",QStringLiteral("")},{"resourceId",QStringLiteral("")},{"allocationEntered",original},
            {"allocationReturned",QVariant()},{"allocationThrew",QVariant()},{"sourceAttached",QVariant()},
            {"destructorBodyEntered",QVariant()},{"deleteEntered",QVariant()},{"deleteReturned",QVariant()},
            {"sizedDelete",QVariant()}};
        owner->rows.append(row);result._state=owner;result._row=quint64(owner->rows.size());return result;
    } catch (...) {fail();return result;}
}
void Observation::allocationReturned(const Token& attempt,void* actual) noexcept {
    Callback callback;if (!callback.entered) {return;}
    try {
        if (!admitted()) {return;}auto owner=std::static_pointer_cast<State>(attempt._state);
        if (!owner || !attempt._row || !actual) {fail();return;}const auto original=owner->phase();
        QMutexLocker lock(&owner->mutex);if (!admitted()) {return;}
        if (attempt._row>quint64(owner->rows.size()) || owner->addresses.contains(actual)) {fail();return;}
        auto& row=owner->rows[int(attempt._row-1)].value;
        if (!row.value("allocationReturned").isNull() || !row.value("allocationThrew").isNull()) {fail();return;}
        row["allocationReturned"]=original;owner->addresses.insert(actual,attempt._row);
    } catch (...) {fail();}
}
void Observation::allocationThrew(const Token& attempt) noexcept {
    Callback callback;if (!callback.entered) {return;}
    try {if (!admitted()) {return;}auto owner=std::static_pointer_cast<State>(attempt._state);
        if (!owner || !attempt._row) {fail();return;}const auto original=owner->phase();
        {
            QMutexLocker lock(&owner->mutex);if (!admitted()) {return;}
            if (attempt._row>quint64(owner->rows.size()) || !owner->rows[int(attempt._row-1)].value.value("allocationReturned").isNull()) {fail();return;}
        }
        setPhase(owner,attempt._row,"allocationThrew",original);
    } catch (...) {fail();}
}
void Observation::attach(void* actual,const image::e2e::IOSImageProcessingObservation::Task& task) noexcept {
    Callback callback;if (!callback.entered) {return;}
    try {
        if (!admitted()) {return;}auto owner=acquire();if (!owner || !mainThread()) {fail();return;}
        if (!identity(task.source1Instance) || !identity(task.taskId) || !identity(task.resourceId) || task.marker.expired()) {fail();return;}
        const auto original=owner->phase();QMutexLocker lock(&owner->mutex);if (!admitted()) {return;}
        const auto found=owner->addresses.constFind(actual);
        if (found==owner->addresses.cend() || (!owner->source1Instance.isEmpty() && owner->source1Instance!=task.source1Instance)) {fail();return;}
        for (const auto& row:owner->rows) {if (row.value.value("taskId")==task.taskId) {fail();return;}}
        auto& row=owner->rows[int(found.value()-1)];
        if (!row.value.value("sourceAttached").isNull()) {fail();return;}
        owner->source1Instance=task.source1Instance;row.marker=task.marker;
        row.value["taskId"]=task.taskId;row.value["resourceId"]=task.resourceId;row.value["sourceAttached"]=original;
    } catch (...) {fail();}
}
void Observation::destructorEntering(void* actual) noexcept {
    Callback callback;if (!callback.entered) {return;}
    try {
        if (!admitted()) {return;}auto owner=acquire();if (!owner) {fail();return;}const auto original=owner->phase();quint64 row=0;
        {
            QMutexLocker lock(&owner->mutex);if (!admitted()) {return;}
            const auto found=owner->addresses.constFind(actual);if (found==owner->addresses.cend()) {fail();return;}row=found.value();
        }
        setPhase(owner,row,"destructorBodyEntered",original);
    } catch (...) {fail();}
}
Observation::Token Observation::deleteEntering(void* actual,std::size_t bytes,bool sized) noexcept {
    Callback callback;if (!callback.entered) {return {};}
    Token result;
    try {
        if (!admitted()) {return result;}auto owner=acquire();if (!owner) {fail();return result;}
        const auto original=owner->phase();QMutexLocker lock(&owner->mutex);if (!admitted()) {return result;}
        const auto found=owner->addresses.find(actual);if (found==owner->addresses.end()) {fail();return result;}
        const auto index=found.value();auto& row=owner->rows[int(index-1)].value;
        if (!row.value("deleteEntered").isNull() || (sized && row.value("storageBytes").toULongLong()!=bytes)) {fail();return result;}
        row["deleteEntered"]=original;row["sizedDelete"]=sized;
        // Capture the exact generation and diagnostic State BEFORE global
        // deallocation. Never inspect the address or dead object afterward.
        result._state=owner;result._row=index;owner->addresses.erase(found);return result;
    } catch (...) {fail();return result;}
}
void Observation::deleteReturned(const Token& captured) noexcept {
    Callback callback;if (!callback.entered) {return;}
    try {if (!admitted()) {return;}auto owner=std::static_pointer_cast<State>(captured._state);
        if (!owner || !captured._row) {fail();return;}const auto original=owner->phase();
        setPhase(owner,captured._row,"deleteReturned",original);
    } catch (...) {fail();}
}
void Observation::disarm() noexcept {
    fail();armed.store(false,std::memory_order_release);
    try {auto old=std::atomic_exchange_explicit(publication(),Pin{},std::memory_order_acq_rel);}
    catch (...) {fail();}
}
QVariantMap Observation::snapshot() noexcept {
    Callback callback;if (!callback.entered) {return {};}
    try {
        if (!admitted() || !mainThread()) {return {};}auto owner=acquire();if (!owner) {return {};}
        QVariantMap result;
        {
            QMutexLocker lock(&owner->mutex);if (!admitted() || owner->source1Instance.isEmpty()) {return {};}
            QVariantList rows;
            for (const auto& row:owner->rows) {auto value=row.value;value["derivedMarkerAlive"]=!row.marker.expired();rows.append(value);}
            result={{"assetImageReaderStorageHistoryVersion",1},{"instance",owner->instance},{"source1Instance",owner->source1Instance},
                {"complete",true},{"clockDomain","native-assets-image-reader-storage"},{"clock",owner->clock()},{"allocations",rows},
                {"byteCopyCompletionAvailable",false},{"poolCompletionAvailable",false},{"decoderCompletionAvailable",false},
                {"gpuCompletionAvailable",false},{"resourceRetirementAvailable",false}};
        }
        return admitted() ? result : QVariantMap{};
    } catch (...) {fail();return {};}
}
} // namespace overte::e2e
#endif
