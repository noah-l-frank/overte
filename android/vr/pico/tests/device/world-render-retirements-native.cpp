// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <PicoWorldRenderRetirements.h>
#include <PrivateWorldRenderReceipts.h>
#include <AudioSettingsQueue.h>
#include <QMutex>
#include <QMutexLocker>
#include <QTemporaryDir>
#include <memory>
#include <stdexcept>
#include <thread>

static void require(bool value) { if(!value) { throw std::runtime_error("Original native retirement counterexample failed"); } }
static QString nonce(int value) { return QString("%1").arg(value,32,16,QLatin1Char('0')); }
class Ledger {
public:
    QMutex _mutex;QString _instance=nonce(60000),_active,_callback;QByteArray _png;
    QSet<QString> _retired,_declinedReceipts;QHash<QString,QPair<QString,QByteArray>> _receipts;
    QString instance() const { return _instance; }
    GPU_INVENTORY_BODY
    GPU_ENABLED_BODY
    GPU_VALID_BODY
};
struct Lifecycle { QVariantMap snapshot() const { return {{"hostLifecycleSeam",true}}; } };
struct Context { std::shared_ptr<Ledger> state=std::make_shared<Ledger>();auto featureWorldRender() { return state; } };
struct App:public QObject {
    std::shared_ptr<Context> context=std::make_shared<Context>();bool hmd=true;
    auto getGPUContext() { return context; }bool isHMDMode() const { return hmd; }
};
// Lifecycle/application/HMD production is an explicit harness seam. Actual
// QObject affinity, queued delivery and cancellation execute unchanged.
struct QGuiApplication { static Qt::ApplicationState applicationState() { return Qt::ApplicationActive; } };
#undef qApp
static App* qApp;
class TestScriptingInterface:public QObject {
public:
    QString _testResultsLocation;std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
    QSet<QString> _featureWorldReceiptsRequests;quint64 _featureWorldReceiptsSequence=0;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureWorldRetirementsQueue=std::make_shared<overte::e2e::AudioSettingsQueue>();
    QSet<QString> _featureWorldRetirementsRequests;quint64 _featureWorldRetirementsSequence=0;
    QVariantMap featureWorldRenderReceipts(const QVariantMap& command);
    QVariantMap featurePicoWorldRenderRetirements(const QVariantMap& command);
};
TSI_RECEIPTS_BODY
TSI_BATCH_BODY

int main(int argc,char** argv) {
    QCoreApplication application(argc,argv);App app;qApp=&app;
    QTemporaryDir files;require(files.isValid());TestScriptingInterface original;original._testResultsLocation=files.path();
    auto ledger=app.context->state;QVariantList captures;
    for(int i=0;i<80;++i) {
        const auto capture=nonce(i+1),receipt=nonce(i+1000);ledger->_retired.insert(capture);
        const QByteArray bytes="actual private original receipt "+receipt.toUtf8();
        const auto hash=QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex();
        ledger->_receipts.insert(receipt,qMakePair(capture,hash));
        captures.append(QVariantMap{{"requestId",capture},{"receiptIds",QStringList{receipt}}});
    }
    quint64 sequence=0;int calls=0;
    auto query=[&](const QVariantMap& value) { ++calls;return original.featureWorldRenderReceipts(value); };
    QVariantMap request{{"schemaVersion",1},{"commandId",nonce(20000)},
        {"action","feature-pico-world-render-retirements"},{"runId",nonce(30000)},{"captures",captures}};
    const auto packet=overte::e2e::picoWorldRetirementsObservation(request,sequence,query);
    require(packet.value("captures").toList().size()==80 && calls==80 && sequence==1);
    qlonglong cursor=0;QSet<QString> commands;
    for(const auto& value:packet.value("captures").toList()) {
        const auto sample=value.toMap();require(sample.value("operation")==QVariant("inspect"));
        require(sample.value("sequence").toLongLong()>cursor);cursor=sample.value("sequence").toLongLong();
        require(!commands.contains(sample.value("commandId").toString()));commands.insert(sample.value("commandId").toString());
        const auto source=sample.value("source").toMap();require(source.value("retired").toBool() && source.value("complete").toBool());
        const auto row=source.value("receipts").toList().first().toMap();require(row.value("issued").toBool() && !row.value("exists").toBool());
    }
    // A real original file remains visible, never removed by the batch reader.
    const auto path=files.path()+"/world-render-storage-"+nonce(1000)+".json";QFile file(path);
    require(file.open(QIODevice::WriteOnly));require(file.setPermissions(QFile::ReadOwner|QFile::WriteOwner));
    require(file.write("actual private original receipt "+nonce(1000).toUtf8())>0);file.close();
    auto present=overte::e2e::picoWorldRetirementsObservation(request,sequence,query);
    require(!present.isEmpty() && present.value("captures").toList().first().toMap().value("source").toMap()
        .value("receipts").toList().first().toMap().value("exists").toBool() && QFile::exists(path));
    require(file.open(QIODevice::WriteOnly|QIODevice::Truncate));require(file.write("foreign replacement")>0);file.close();
    require(overte::e2e::picoWorldRetirementsObservation(request,sequence,query).isEmpty());require(QFile::exists(path));
    require(QFile::remove(path));ledger->_callback=nonce(1);
    require(overte::e2e::picoWorldRetirementsObservation(request,sequence,query).isEmpty());ledger->_callback.clear();
    auto bad=request;bad.insert("expectedAbsent",true);calls=0;
    require(overte::e2e::picoWorldRetirementsObservation(bad,sequence,query).isEmpty() && calls==0);
    bad=request;bad.insert("schemaVersion",true);require(!overte::e2e::picoWorldRetirementsCommand(bad));
    auto duplicate=captures;duplicate.append(captures.first());bad=request;bad.insert("captures",duplicate);
    require(!overte::e2e::picoWorldRetirementsCommand(bad));
    // The complete new TSI method preserves original queue settlement and
    // consumes unavailable queries. Duplicate commands never re-read sources.
    auto queued=request;queued.insert("commandId",nonce(22000));queued.insert("captures",QVariantList{captures.first()});
    const auto first=original.featurePicoWorldRenderRetirements(queued);require(!first.isEmpty());
    const auto used=original._featureWorldReceiptsRequests.size();
    require(original.featurePicoWorldRenderRetirements(queued).isEmpty());require(original._featureWorldReceiptsRequests.size()==used);
    ledger->_callback=nonce(1);queued.insert("commandId",nonce(22001));
    require(original.featurePicoWorldRenderRetirements(queued).isEmpty());ledger->_callback.clear();
    require(original.featurePicoWorldRenderRetirements(queued).isEmpty());
    app.hmd=false;queued.insert("commandId",nonce(22002));require(original.featurePicoWorldRenderRetirements(queued).isEmpty());app.hmd=true;
    QVariantMap threaded;std::atomic<bool> done{false};queued.insert("commandId",nonce(22003));
    std::thread worker([&] { threaded=original.featurePicoWorldRenderRetirements(queued);done.store(true); });
    while(!done.load()) { QCoreApplication::processEvents();QThread::msleep(1); }
    worker.join();require(!threaded.isEmpty());
    // A real undispatched Qt functor times out. Its callback is never invoked
    // after cancellation, and the original queue remains owned until reaped.
    queued.insert("commandId",nonce(22004));
    std::thread blocked([&] { threaded=original.featurePicoWorldRenderRetirements(queued); });blocked.join();require(threaded.isEmpty());
    queued.insert("commandId",nonce(22005));require(original.featurePicoWorldRenderRetirements(queued).isEmpty());
    QCoreApplication::processEvents();require(original.featurePicoWorldRenderRetirements(queued).isEmpty()==false);
    // The existing getter cap is unchanged and failure does not turn into an
    // empty successful inventory or bypass the original issuer validation.
    for(int i=0;original._featureWorldReceiptsRequests.size()<4096;++i) { original._featureWorldReceiptsRequests.insert(nonce(40000+i)); }
    require(overte::e2e::picoWorldRetirementsObservation(request,sequence,query).isEmpty());
    original._featureWorldReceiptsRequests.clear();
    auto slow=[&](const QVariantMap& value) { auto result=query(value);QThread::msleep(1500);return result; };
    bad=request;bad.insert("captures",QVariantList{captures.first()});
    require(overte::e2e::picoWorldRetirementsObservation(bad,sequence,slow).isEmpty());
    return 0;
}
