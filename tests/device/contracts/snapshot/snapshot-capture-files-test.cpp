// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Fixed Phone5527 original save/FD test seams, selected for actual Pico bodies.
#include <iostream>
#include <QTemporaryDir>
#include "interface/src/ui/SnapshotCapture.h"
#include <thread>
#include "tests/device/native/FeatureLifecycle.h"
#include "tests/device/native/AudioSettingsQueue.h"
#include "tests/device/native/PrivatePreviewFiles.h"

#include <QCoreApplication>
#include <QImage>
#include <QUrl>
#include <QRegularExpression>
#include <QTemporaryFile>
#include <QDebug>
#include <QJsonDocument>
#include "interface/src/ui/SnapshotStorage.h"
#include "tests/device/native/PicoSnapshotCaptureFiles.h"
struct AddressManager { QUrl currentPublicAddress(){return QUrl("https://controlled.invalid/source-only");} };
struct AccountInfo { QString getUsername(){return "synthetic-host-user";} };
struct AccountManager { AccountInfo getAccountInfo(){return {};} };
struct DependencyManager { inline static bool available{true};template<class T>static bool isSet(){return available;} template<class T>static T* get(){static T value;return &value;} };
struct Reticle { void setVisible(bool){} void setAllowMouseCapture(bool){} };
struct Compositor { Reticle* getReticleInterface(){static Reticle value;return &value;} };
struct FakeApp { bool hmd{true};bool isHMDMode(){return hmd;}  Compositor& getApplicationCompositor(){static Compositor value;return value;} };
static FakeApp fakeApp;
#undef qApp
#define qApp (&fakeApp)
struct OffscreenUi { static QString getExistingDirectory(void*,const QString&,const QString&){throw std::runtime_error("Unplanned host UI");} };
struct Location { void set(const QString&){} };
static const QString URL="overte_url",DEFAULT_FORMAT="png",FILENAME_PATH_FORMAT="overte-snap-by-%1-on-%2",DATETIME_FORMAT="yyyy-MM-dd_hh-mm-ss";
static const QList<QString> SUPPORTED_IMAGE_FORMATS={"jpg","jpeg","png","webp"};
struct WindowScriptingInterface { void snapshot360Taken(const QString&,bool) {} };
class Snapshot {
public:
    QString saveSnapshot(QImage image,const QString& filename,const QString& pathname=QString());
    QFile* savedFileForSnapshot(QImage& image,bool temporary,const QString& filename=QString(),const QString& pathname=QString());
    bool nativeReviewEnabled(){return true;}
    QString getSnapshotsLocation(){return overte::snapshot::storageRoot();}
    QString getSnapshotFormat(){return "png";}
    Location _snapshotsLocation;QString actualPath;
    void complete360(const QImage&,const QString&,bool,const SnapshotCapture&);
    void captureStatus(const SnapshotCapture& capture,const QString& phase,const QString& path,const QString& ={}) {
        actualPath=path;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        overte::e2e::PicoSnapshotCaptureFiles::get().terminal(capture->id,phase,path);
#else
        Q_UNUSED(capture) Q_UNUSED(phase)
#endif
    }
};

#include "original-snapshot-save.inc"

#if defined(OVERTE_E2E_FEATURE_TESTS)
class TestScriptingInterface:public QObject {
public:QVariantMap featurePicoSnapshotCaptureFiles(const QVariantMap& command);
    QString _testResultsLocation,_featureObservationInstance{QString(32,'f')};
    overte::e2e::FeatureLifecycle* _featureLifecycle{nullptr};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QSet<QString> _featureSnapshotFileQueries;quint64 _featureSnapshotFileSequence{0};
};
#include "original-snapshot-files-getter.inc"
#endif

static void need(bool value){if(!value)throw std::runtime_error("Original capture file source contract");}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);QCoreApplication::setApplicationName("actual-capture-files");Snapshot service;
    const QString mode=argv[1],root=overte::snapshot::storageRoot();need(QDir().mkpath(root));
    const QString run(32,'a'),planId(32,'b'),operation(32,'c'),prefix="e2e-"+run,capture="original_native_capture_1",name=prefix+"-"+capture+".png",path=QDir(root).filePath(name);
    QImage image(64,48,QImage::Format_ARGB32);image.fill(Qt::cyan);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    using overte::e2e::PicoSnapshotCaptureFiles;auto& owner=PicoSnapshotCaptureFiles::get();
    if(!app.arguments().contains("--testScript")) {
        need(!owner.plan(run,prefix,planId,root));need(!service.saveSnapshot(image,name).isEmpty() && owner.snapshot().isEmpty());return 0;
    }
    if(mode=="foreign") { QFile old(path);need(old.open(QIODevice::WriteOnly));need(old.write("prior-user-capture")==18);old.close();need(!owner.plan(run,prefix,planId,root)); }
    else need(owner.plan(run,prefix,planId,root));
    owner.begin(capture);std::unique_ptr<PicoSnapshotCaptureFiles::Scope> scope;
    if(mode!="360")scope=std::make_unique<PicoSnapshotCaptureFiles::Scope>(capture);
    if(mode=="partial")image=QImage();
    if(mode=="pending" || mode=="pending-close") {
        const auto ticket=owner.opening(path,root);QFile actual(path);need(actual.open(QIODevice::WriteOnly));owner.opened(ticket,actual.handle());need(actual.write("real partial original")==21);
        need(!owner.retire(run,ticket,operation));
        owner.beforeClose(ticket,actual.handle());
        if(mode=="pending-close") { owner.closed(ticket,actual.isOpen());owner.terminal(capture,"cancelled",{});need(!owner.retire(run,ticket,operation));return 0; }
        actual.close();owner.closed(ticket,actual.isOpen());owner.terminal(capture,"cancelled",{});need(owner.retire(run,ticket,operation));return 0;
    }
    QString saved;
    if(mode=="360") {service.complete360(image,name,false,std::make_shared<SnapshotCaptureRequest>(capture));saved=service.actualPath;}
    else saved=service.saveSnapshot(image,name);
    need((mode=="partial")==saved.isEmpty());
    if(mode!="360")owner.terminal(capture,mode=="partial" ? "error" : mode=="cancelled" ? "cancelled" : "complete",mode=="partial" || mode=="cancelled" ? QString() : path);
    auto original=owner.snapshot();auto rows=original.value("rows").toList();need(original.value("complete")==true && rows.size()==1);
    auto row=rows[0].toMap();const auto id=row.value("id").toString();need(row.value("closed")==true && row.value("opened")==true);
    if(mode=="foreign") { need(row.value("preexisting")==true && row.value("planId").toString().isEmpty() && !owner.retire(run,id,operation) && QFileInfo(path).exists());return 0; }
    need(row.value("planId")==planId && row.value("runId")==run && row.value("preexisting")==false);
    if(mode!="partial") {
        QFile actual(path);need(actual.open(QIODevice::ReadOnly));const auto bytes=actual.readAll();actual.close();
        need(row.value("bytes").toLongLong()==bytes.size() && row.value("sha256")==QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()));
    }
    if(mode=="changed-inode") {
        need(QFile::rename(path,path+".old"));QFile replacement(path);need(replacement.open(QIODevice::WriteOnly));QFile old(path+".old");need(old.open(QIODevice::ReadOnly));replacement.write(old.readAll());replacement.close();old.close();
        need(!owner.retire(run,id,operation) && QFileInfo(path).exists());return 0;
    }
    if(mode=="fifo") {
        need(QFile::rename(path,path+".old") && ::mkfifo(QFile::encodeName(path).constData(),0600)==0);
        QElapsedTimer elapsed;elapsed.start();need(!owner.retire(run,id,operation) && elapsed.elapsed()<200 && QFileInfo(path).exists());return 0;
    }
    if(mode=="changed-bytes") { QFile changed(path);need(changed.open(QIODevice::ReadWrite));auto one=changed.read(1);need(one.size()==1 && changed.seek(0));one[0]=char(one[0]^1);changed.write(one);changed.close();need(!owner.retire(run,id,operation) && QFileInfo(path).exists());return 0; }
    if(mode=="early-missing") { need(QFile::remove(path));need(!owner.retire(run,id,operation));return 0; }
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'d')},{"action","pico-snapshot-files-observe"},{"runId",run}};quint64 sequence=0;
    for(const auto& key:QStringList{"path","sha256","expected","fileId"}) { auto foreign=command;foreign[key]="foreign";need(overte::e2e::picoSnapshotCaptureFileObservation(foreign,QString(32,'f'),sequence).isEmpty()); }
    TestScriptingInterface bridge;QTemporaryDir privateRoot;need(privateRoot.isValid());
    bridge._testResultsLocation=privateRoot.path();overte::e2e::FeatureLifecycle lifecycle(&bridge);
    need(lifecycle.start(privateRoot.path()));bridge._featureLifecycle=&lifecycle;
    fakeApp.hmd=false;need(bridge.featurePicoSnapshotCaptureFiles(command).isEmpty());fakeApp.hmd=true;
    DependencyManager::available=false;need(bridge.featurePicoSnapshotCaptureFiles(command).isEmpty());DependencyManager::available=true;
    if(mode=="success") {
        QVariantMap late;QElapsedTimer timer;timer.start();
        std::thread worker([&] {late=bridge.featurePicoSnapshotCaptureFiles(command);});worker.join();
        need(late.isEmpty() && timer.elapsed()<1800 && bridge.featurePicoSnapshotCaptureFiles(command).isEmpty());
        QCoreApplication::sendPostedEvents();QCoreApplication::processEvents();
    }
    const auto packet=bridge.featurePicoSnapshotCaptureFiles(command);
    need(bridge.featurePicoSnapshotCaptureFiles(command).isEmpty());need(!packet.isEmpty());
    std::cout<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
    need(owner.retire(run,id,operation) && !QFileInfo(path).exists());need(owner.retire(run,id,operation));need(!owner.retire(run,id,QString(32,'e')));
    if(mode=="late-file") { QFile late(path);need(late.open(QIODevice::WriteOnly));late.write("late");late.close();need(!owner.retire(run,id,operation));need(owner.snapshot().value("complete")==false && QFileInfo(path).exists());return 0; }
    need(owner.seal(run,planId,QString(32,'7')));need(owner.seal(run,planId,QString(32,'7')));
    if(mode=="late-namespace") { QFile late(QDir(root).filePath(prefix+"-unknown.png"));need(late.open(QIODevice::WriteOnly));late.write("late");late.close();need(owner.snapshot().value("complete")==false);return 0; }
    if(mode=="new-scope") { need(owner.plan(QString(32,'8'),"e2e-"+QString(32,'8'),QString(32,'9'),root));owner.begin("new_original_capture"); }
    command["commandId"]=QString(32,'e');const auto retired=overte::e2e::picoSnapshotCaptureFileObservation(command,QString(32,'f'),sequence);
    std::cout<<QJsonDocument::fromVariant(retired).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
#else
    need(!service.saveSnapshot(image,name).isEmpty() && QFileInfo(path).exists());
#endif
    return 0;
}
