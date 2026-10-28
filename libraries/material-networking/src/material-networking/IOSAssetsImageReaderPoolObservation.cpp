// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSAssetsImageReaderPoolObservation.h"
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#if defined(OVERTE_E2E_RUNNABLE_POOL_PRIVATE_API)
#include <QtCore/private/qthreadpool_p.h>
#endif
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <atomic>
#include <cstring>
#include <memory>

namespace overte::e2e {
namespace {
std::atomic<bool> attempted{false},armed{false},failed{false};
static_assert(std::atomic<bool>::is_always_lock_free);
void fail() noexcept {failed.store(true,std::memory_order_release);}
bool admitted() noexcept {return armed.load(std::memory_order_acquire) && !failed.load(std::memory_order_acquire);}
bool mainThread() noexcept {auto* app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread();}
QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
bool identity(const QString& value) {
    if (value.size()!=32) {return false;}
    for (const auto c:value) {if (!((c>='0' && c<='9') || (c>='a' && c<='f'))) {return false;}}
    return true;
}
struct State {
    State() {timer.start();}
    QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",timer.elapsed()}};}
    QMutex mutex;QElapsedTimer timer;QString instance{nonce()},source1Instance;QVector<QVariantMap> bindings;bool shutdownBound{false};
};
using Pin=std::shared_ptr<State>;
Pin* publication() {static Pin* const value=new Pin;return value;}
Pin acquire() {return std::atomic_load_explicit(publication(),std::memory_order_acquire);}
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
static_assert(QT_OVERTE_E2E_RUNNABLE_POOL==1);
QOverteE2ePoolKey key(const QString& value) {
    QOverteE2ePoolKey result;bool a=false,b=false;
    if (identity(value)) {result.high=value.left(16).toULongLong(&a,16);result.low=value.mid(16).toULongLong(&b,16);}
    if (!a || !b || !(result.high || result.low)) {fail();return {};}
    return result;
}
QString text(QOverteE2ePoolKey value) {
    return QStringLiteral("%1%2").arg(value.high,16,16,QLatin1Char('0')).arg(value.low,16,16,QLatin1Char('0'));
}
#endif
} // namespace

void IOSAssetsImageReaderPoolObservation::bootstrap(int argc,const char* const* argv) noexcept {
    bool selected=false;
    for (int i=1;i<argc;++i) {
        if (!argv[i]) {continue;}
        if (std::strcmp(argv[i],"--testScript")==0 && i+1<argc && argv[i+1] && argv[i+1][0]) {selected=true;}
        if (std::strncmp(argv[i],"--testScript=",13)==0 && argv[i][13]) {selected=true;}
    }
    if (!selected) {return;}
    if (attempted.exchange(true,std::memory_order_acq_rel)) {fail();return;}
    try {
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
        if (std::strcmp(qVersion(),"6.11.1")!=0 || QCoreApplication::instance()) {fail();return;}
        auto owner=std::make_shared<State>();
        if (!qOverteE2ePoolArm(key(owner->instance)) || !qOverteE2ePoolHealthy()) {fail();return;}
        std::atomic_store_explicit(publication(),owner,std::memory_order_release);armed.store(true,std::memory_order_release);
#else
        fail(); // Optional matching SDK absent; never invoke a guessed API.
#endif
    } catch (...) {fail();}
}
quint64 IOSAssetsImageReaderPoolObservation::registration(QRunnable* actual,const QString& allocation,const QString& source1,
        const QString& task,const QString& resource) noexcept {
    try {
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
        auto owner=acquire();if (!admitted() || !owner) {return 0;}
        if (!mainThread() || !actual || !identity(allocation) || !identity(source1) || !identity(task) || !identity(resource)) {fail();return 0;}
        if (!owner->shutdownBound) {
            auto* app=QCoreApplication::instance();
            const auto quit=QObject::connect(app,&QCoreApplication::aboutToQuit,app,[] {IOSAssetsImageReaderPoolObservation::disarm();},Qt::DirectConnection);
            const auto destroyed=QObject::connect(app,&QObject::destroyed,app,[] {IOSAssetsImageReaderPoolObservation::disarm();},Qt::DirectConnection);
            if (!quit || !destroyed) {fail();return 0;}owner->shutdownBound=true;
        }
        // The Core API owns only a raw registration/generation, never an app
        // object. This call is outside Source1/Storage/Pool observation locks.
        const auto id=qOverteE2ePoolRegister(actual,key(allocation));
        const auto original=owner->clock();
        if (!id || !qOverteE2ePoolHealthy()) {fail();return 0;}
        QMutexLocker lock(&owner->mutex);
        if (!admitted() || owner->bindings.size()>=64 || (!owner->source1Instance.isEmpty() && owner->source1Instance!=source1)) {fail();return 0;}
        for (const auto& row:owner->bindings) {if (row.value("registrationId").toULongLong()==id || row.value("allocationId")==allocation || row.value("taskId")==task) {fail();return 0;}}
        owner->source1Instance=source1;owner->bindings.append({{"registrationId",id},{"allocationId",allocation},
            {"taskId",task},{"resourceId",resource},{"attached",original}});return id;
#else
        Q_UNUSED(actual);Q_UNUSED(allocation);Q_UNUSED(source1);Q_UNUSED(task);Q_UNUSED(resource);return 0;
#endif
    } catch (...) {fail();return 0;}
}
void IOSAssetsImageReaderPoolObservation::retiring(quint64 id) noexcept {
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
    if (!id || !admitted()) {return;}
    if (!qOverteE2ePoolRetire(id)) {fail();}
#else
    Q_UNUSED(id);
#endif
}
void IOSAssetsImageReaderPoolObservation::disarm() noexcept {
    fail();armed.store(false,std::memory_order_release);
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
    qOverteE2ePoolDisarm();
#endif
    try {auto old=std::atomic_exchange_explicit(publication(),Pin{},std::memory_order_acq_rel);}
    catch (...) {fail();}
}
QVariantMap IOSAssetsImageReaderPoolObservation::snapshot() noexcept {
    try {
#if defined(QT_OVERTE_E2E_RUNNABLE_POOL)
        auto owner=acquire();if (!admitted() || !owner || !mainThread() || !qOverteE2ePoolHealthy()) {return {};}
        QVector<QVariantMap> bindings;QString source1;
        {QMutexLocker lock(&owner->mutex);bindings=owner->bindings;source1=owner->source1Instance;}
        if (source1.isEmpty()) {return {};}
        // Allocation and all QVariant/QString construction are on the getter
        // side outside Core pool locks. SDK copy itself touches fixed POD only.
        auto data=std::make_unique<QOverteE2ePoolSnapshot>();
        if (!qOverteE2ePoolCopy(data.get()) || data->version!=1 || !data->healthy || text(data->instance)!=owner->instance
                || data->poolCount>data->MaxPools || data->registrationCount>data->MaxRegistrations
                || data->admissionCount>data->MaxAdmissions || data->eventCount>data->MaxEvents) {fail();return {};}
        QVariantList regs,admissions,events,links;
        for (quint64 i=0;i<data->registrationCount;++i) {
            const auto& row=data->registrations[i];if (!row.id) {continue;}regs.append(QVariantMap{{"id",row.id},{"allocationId",text(row.allocation)},{"live",row.live}});
        }
        for (quint64 i=0;i<data->admissionCount;++i) {
            const auto& row=data->admissions[i];if (!row.id) {continue;}admissions.append(QVariantMap{{"id",row.id},{"poolId",row.pool},
                {"registrationId",row.registration},{"operation",quint32(row.operation)}});
        }
        for (quint64 i=0;i<data->eventCount;++i) {
            const auto& row=data->events[i];if (!row.sequence) {continue;}events.append(QVariantMap{{"sequence",row.sequence},{"kind",quint32(row.kind)},
                {"poolId",row.pool},{"registrationId",row.registration},{"admissionId",row.admission},{"slotId",row.slot},
                {"threadSlotId",row.thread},{"operationId",row.operation},{"epochMs",row.epochMs},{"steadyNs",QString::number(row.steadyNs)},{"flags",row.flags}});
        }
        for (const auto& row:bindings) {links.append(row);}
        QVariantMap result={{"assetImageReaderPoolHistoryVersion",1},{"instance",owner->instance},{"source1Instance",source1},
            {"complete",true},{"clockDomain","native-assets-image-reader-pool"},{"clock",owner->clock()},
            {"bindings",links},{"qt",QVariantMap{{"qtRunnablePoolProtocolVersion",1},{"instance",text(data->instance)},
                {"clockDomain","qtcore-runnable-pool-steady-nanoseconds"},{"epochMs",data->epochMs},{"steadyNs",QString::number(data->steadyNs)},
                {"healthy",data->healthy},{"cutComplete",data->cutComplete},{"mutationSerial",data->mutationSerial},{"inFlight",data->inFlight},
                {"poolCount",data->poolCount},{"reservedRegistrations",data->registrationCount},{"reservedAdmissions",data->admissionCount},{"reservedEvents",data->eventCount},{"registrations",regs},{"admissions",admissions},{"events",events}}},
            {"byteCopyCompletionAvailable",false},{"globalPoolCompletionAvailable",false},{"decoderCompletionAvailable",false},
            {"gpuCompletionAvailable",false},{"resourceRetirementAvailable",false}};
        return admitted() && qOverteE2ePoolHealthy() ? result : QVariantMap{};
#else
        return {};
#endif
    } catch (...) {fail();return {};}
}
} // namespace overte::e2e
#endif
