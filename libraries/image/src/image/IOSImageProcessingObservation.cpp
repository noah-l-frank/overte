// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSImageProcessingObservation.h"
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <atomic>
#include <exception>

namespace image::e2e {
namespace {
using Observation=IOSImageProcessingObservation;
std::atomic<bool> failed{false},armed{false};
static_assert(std::atomic<bool>::is_always_lock_free);
void fail() noexcept {failed.store(true,std::memory_order_release);}
bool admitted() noexcept {return armed.load(std::memory_order_acquire) && !failed.load(std::memory_order_acquire);}
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
struct TaskEntry {QVariantMap value;std::weak_ptr<void> marker;};
struct Call {QVariantMap value;std::weak_ptr<QIODevice> device;};
struct State {
    State() {timer.start();}
    QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",timer.elapsed()}};}
    QVariantMap phase() const {auto result=clock();result["threadContextId"]=threadContext();return result;}
    QMutex mutex;QElapsedTimer timer;QString instance{nonce()},source1Instance;
    QVector<TaskEntry> tasks;QVector<Call> calls;
};
using Pin=std::shared_ptr<State>;
Pin* publication() {static Pin* const slot=new Pin;return slot;}
Pin acquire() {return std::atomic_load_explicit(publication(),std::memory_order_acquire);}
thread_local Observation::Binding* pending=nullptr;
thread_local quint64 active=0;
thread_local unsigned depth=0;
void setPhase(const Pin& owner,quint64 row,const char* name,const QVariantMap& original) {
    QMutexLocker lock(&owner->mutex);
    if (!admitted()) {return;}
    if (!row || row>quint64(owner->calls.size())) {fail();return;}
    auto& value=owner->calls[int(row-1)].value;
    if (!value.value(name).isNull()) {fail();return;}
    value[name]=original;
}
void event(const char* name) noexcept {
    try {auto owner=acquire();if (!admitted() || !owner || !active) {return;}
        const auto original=owner->phase();setPhase(owner,active,name,original);
    } catch (...) {fail();}
}
} // namespace

Observation::Task Observation::prepare(Task actual) noexcept {
    try {
        if (!gate() || failed.load(std::memory_order_acquire)) {return {};}
        if (!identity(actual.source1Instance) || !identity(actual.taskId) || !identity(actual.resourceId) || actual.token || actual.marker.expired()) {fail();return {};}
        auto owner=acquire();
        if (!owner) {
            owner=std::make_shared<State>();auto* app=QCoreApplication::instance();
            const auto quit=QObject::connect(app,&QCoreApplication::aboutToQuit,app,[] {Observation::disarm();},Qt::DirectConnection);
            const auto destroyed=QObject::connect(app,&QObject::destroyed,app,[] {Observation::disarm();},Qt::DirectConnection);
            if (!quit || !destroyed) {fail();return {};}
            std::atomic_store_explicit(publication(),owner,std::memory_order_release);armed.store(true,std::memory_order_release);
        }
        const auto original=owner->phase();
        QMutexLocker lock(&owner->mutex);
        if (!admitted() || owner->tasks.size()>=64 || (!owner->source1Instance.isEmpty() && owner->source1Instance!=actual.source1Instance)) {fail();return {};}
        for (const auto& row:owner->tasks) {if (row.value.value("taskId")==actual.taskId) {fail();return {};}}
        owner->source1Instance=actual.source1Instance;
        TaskEntry entry;entry.marker=actual.marker;entry.value={{"taskId",actual.taskId},{"resourceId",actual.resourceId},{"prepared",original}};
        owner->tasks.append(entry);
        actual.token=quint64(owner->tasks.size());return actual;
    } catch (...) {fail();return {};}
}

Observation::Binding::Binding(const Task& task,const std::shared_ptr<QIODevice>& actual) noexcept {
    // Mask an outer pending call before any diagnostic allocation/Qt connect.
    // Reentrant unbound processing during setup cannot consume that outer call.
    if (depth>=16) {fail();return;}
    _previous=pending;pending=this;++depth;_pushed=true;
    try {
        auto owner=acquire();if (!admitted() || !owner || !task.token) {return;}
        if (!actual) {fail();return;}
        const auto original=owner->phase();
        {
            QMutexLocker lock(&owner->mutex);
            if (!admitted()) {return;}
            if (task.token>quint64(owner->tasks.size()) || owner->source1Instance!=task.source1Instance || owner->calls.size()>=64) {fail();return;}
            const auto& registered=owner->tasks[int(task.token-1)];
            if (registered.value.value("taskId")!=task.taskId || registered.value.value("resourceId")!=task.resourceId) {fail();return;}
            for (const auto& call:owner->calls) {if (call.value.value("taskId")==task.taskId) {fail();return;}}
            Call call;call.device=actual;call.value={{"id",nonce()},{"taskId",task.taskId},{"resourceId",task.resourceId},
                {"deviceId",nonce()},{"bindingEntered",original},{"processingEntered",QVariant()},
                {"processingReturned",QVariant()},{"processingUnwound",QVariant()},{"rawEntered",QVariant()},
                {"rawReturned",QVariant()},{"rawUnwound",QVariant()},{"contentResetEntered",QVariant()},
                {"contentResetReturned",QVariant()},{"deviceDestroyedObserved",QVariant()}};
            owner->calls.append(call);_row=quint64(owner->calls.size());
        }
        // The exact newly constructed actual OwningBuffer is provided by its
        // constructor call site. No observer holds it strongly or reads its
        // QObject properties from another thread. Connect outside our mutex.
        auto* object=actual.get();const auto row=_row;
        const auto connected=QObject::connect(object,&QObject::destroyed,[owner,row,object](QObject* actualObject) noexcept {
            try {
                if (!admitted()) {return;}
                if (actualObject!=object) {fail();return;}
                const auto original=owner->phase();setPhase(owner,row,"deviceDestroyedObserved",original);
            } catch (...) {fail();}
        });
        if (!connected) {fail();return;}
        _ready=true; // Only the actual later processImage entry may claim this binding.
    } catch (...) {fail();}
}
Observation::Binding::~Binding() {
    if (!_pushed) {return;}
    if (pending!=this || !depth) {fail();return;}
    pending=_previous;--depth;
    // No QObject disconnect, Qt API, waiting drain or product ownership change.
}

Observation::Body::Body(Kind kind) noexcept:_kind(kind),_previous(active),_exceptions(std::uncaught_exceptions()) {
    // Every processing entry masks an outer invocation, including unobserved
    // recursive calls. Only an actual unclaimed call-local binding may attach.
    if (kind==Kind::Processing) {if (pending && pending->_ready && !pending->_claimed) {pending->_claimed=true;_row=pending->_row;}active=_row;}
    else {_row=active;}
    try {auto owner=acquire();if (admitted() && owner && _row) {
        const auto original=owner->phase();setPhase(owner,_row,kind==Kind::Processing ? "processingEntered" : "rawEntered",original);
    }} catch (...) {fail();}
}
Observation::Body::~Body() {
    try {auto owner=acquire();if (admitted() && owner && _row) {
        const bool unwound=std::uncaught_exceptions()>_exceptions;const auto original=owner->phase();
        const char* field=_kind==Kind::Processing ? (unwound ? "processingUnwound" : "processingReturned") : (unwound ? "rawUnwound" : "rawReturned");
        setPhase(owner,_row,field,original);
    }} catch (...) {fail();}
    if (_kind==Kind::Processing) {active=_previous;}
}
void Observation::contentResetEntering() noexcept {event("contentResetEntered");}
void Observation::contentResetReturned() noexcept {event("contentResetReturned");}
void Observation::disarm() noexcept {
    fail();armed.store(false,std::memory_order_release);
    try {auto old=std::atomic_exchange_explicit(publication(),Pin{},std::memory_order_acq_rel);}
    catch (...) {fail();}
}
QVariantMap Observation::snapshot() noexcept {
    try {
        if (!admitted() || !mainThread()) {return {};}
        auto owner=acquire();if (!owner) {return {};}
        QVariantMap result;
        {
            QMutexLocker lock(&owner->mutex);if (!admitted() || owner->source1Instance.isEmpty()) {return {};}
            QVariantList calls,tasks;
            for (const auto& call:owner->calls) {auto row=call.value;row["deviceOwnersAlive"]=!call.device.expired();calls.append(row);}
            for (const auto& task:owner->tasks) {auto row=task.value;row["derivedMarkerAlive"]=!task.marker.expired();tasks.append(row);}
            result={{"assetImageReaderProcessingHistoryVersion",1},{"instance",owner->instance},
                {"source1Instance",owner->source1Instance},{"complete",true},{"clockDomain","native-assets-image-reader-processing"},
                {"clock",owner->clock()},{"tasks",tasks},{"calls",calls},{"byteCopyCompletionAvailable",false},
                {"basePoolCompletionAvailable",false},{"decoderCompletionAvailable",false},{"gpuCompletionAvailable",false},
                {"resourceRetirementAvailable",false}};
        }
        return admitted() ? result : QVariantMap{};
    } catch (...) {fail();return {};}
}
} // namespace image::e2e
#endif
