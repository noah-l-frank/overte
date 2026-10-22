// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QCoreApplication>
#include <QGuiApplication>
#include <QTemporaryDir>
#include <QSharedPointer>
#include <QElapsedTimer>
#include "tests/device/native/FeatureLifecycle.h"
#include "tests/device/native/PrivatePreviewFiles.h"
#include "tests/device/native/AudioSettingsQueue.h"
#include <QImage>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QThread>
#include <QTimer>
#include <array>
#include <cassert>
#include <thread>
#include "interface/src/ui/SnapshotCapture.h"
#include "tests/device/native/SnapshotCaptureOriginals.h"

struct SnapshotAnimated {static void cancelCapture(const SnapshotCapture&) {}};
class Snapshot : public QObject {
    Q_OBJECT
public:
    SnapshotCapture beginCapture(const QString& requestId);
    void captureStatus(const SnapshotCapture&,const QString&,const QString& path={},const QString& error={});
    void cancelCapture(const QString&);
    QVariantMap featureSnapshotCaptureOriginals(const QVariantMap&);
    // Renderer, platform and secondary camera are explicit host boundaries.
    bool nativeReviewEnabled() const {return false;}
    void restoreSecondaryCamera() {}
    QHash<QString,SnapshotCapture> _captures;
    QMutex _captureMutex;
    SnapshotCapture _capture360;
    QTimer _snapshotTimer;
    bool _taking360Snapshot{false},_waitingOnSnapshot{false};
    std::array<QImage,6> _imageArray;
    overte::e2e::SnapshotCaptureOriginals _featureCaptureOriginals;
signals:
    void captureStatusChanged(const QString&,const QString&,const QString&,const QString&);
};
#include "snapshot-originals-test.moc"
#include "original-snapshot.inc"

class HostApplication : public QGuiApplication {
public:
    using QGuiApplication::QGuiApplication;
    bool hmd{true};
    bool isHMDMode() const {return hmd;}
};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
namespace DependencyManager {
static QSharedPointer<Snapshot> original;
template<class T> bool isSet() {return bool(original);}
template<class T> QSharedPointer<T> get() {return qSharedPointerCast<T>(original);}
}
class TestScriptingInterface : public QObject {
public:
    QVariantMap featureSnapshotCaptureOriginals(const QVariantMap&);
    QString _testResultsLocation;
    overte::e2e::FeatureLifecycle* _featureLifecycle{nullptr};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
};
#include "original-snapshot-getter.inc"

static QVariantMap command(const QString& operation="read") {
    static int index=0;
    return {{"schemaVersion",1.0},{"commandId",QString::number(++index,16).rightJustified(32,'0')},
        {"runId",QString(32,'a')},{"operation",operation}};
}
static QVariantList rows(Snapshot& owner) {return owner.featureSnapshotCaptureOriginals(command()).value("requests").toList();}
static void queued() {QCoreApplication::sendPostedEvents();QCoreApplication::processEvents();}
int main(int argc,char** argv) {
    HostApplication app(argc,argv);Snapshot owner;
    const auto armed=owner.featureSnapshotCaptureOriginals(command("arm"));
    if(!app.arguments().contains("--testScript")) {assert(armed.isEmpty());return 0;}
    assert(!armed.isEmpty());assert(armed.value("requests").toList().isEmpty());
    assert(owner.featureSnapshotCaptureOriginals(command("arm")).isEmpty());
    auto malformed=command();malformed.insert("expectedPhase","complete");
    assert(owner.featureSnapshotCaptureOriginals(malformed).isEmpty());
    auto foreign=command();foreign.insert("runId",QString(32,'b'));
    assert(owner.featureSnapshotCaptureOriginals(foreign).isEmpty());
    const auto id=QStringLiteral("snap_1234_1");auto original=owner.beginCapture(id);
    assert(original);const auto birth=rows(owner).at(0).toMap().value("birth");
    assert(rows(owner).at(0).toMap().value("alive").toBool());
    assert(rows(owner).at(0).toMap().value("events").toList().isEmpty());
    int emitted=0;QObject::connect(&owner,&Snapshot::captureStatusChanged,[&](auto,auto,auto,auto){++emitted;});
    // The actual cross-thread body queues its original shared request. Dropping
    // our variable cannot retire that real queued functor before its callback.
    std::thread worker([&]{owner.captureStatus(original,"complete","/explicit-host/capture.png");});worker.join();
    original.reset();auto before=rows(owner).at(0).toMap();
    assert(before.value("alive").toBool());assert(before.value("events").toList().isEmpty());assert(emitted==0);
    queued();auto completed=rows(owner).at(0).toMap();
    assert(!completed.value("alive").toBool());assert(completed.value("nativeState").toString().isEmpty());
    const auto events=completed.value("events").toList();assert(events.size()==1);
    assert(events.at(0).toMap().value("phase")=="complete");assert(emitted==1);
    assert(!events.at(0).toMap().value("basenameSha256").toString().isEmpty());
    auto cancelled=owner.beginCapture("snap_1234_2");assert(cancelled);
    owner.cancelCapture(cancelled->id);owner.captureStatus(cancelled,"complete","/late/ignored.png");
    auto pending=rows(owner).at(1).toMap();assert(pending.value("nativeState")=="cancelled");
    assert(pending.value("events").toList().isEmpty());cancelled.reset();queued();
    auto stopped=rows(owner).at(1).toMap();assert(!stopped.value("alive").toBool());
    assert(stopped.value("events").toList().size()==1);
    assert(stopped.value("events").toList().at(0).toMap().value("phase")=="cancelled");assert(emitted==2);
    // Reusing a textual native ID still creates a distinct actual controlblock.
    auto reused=owner.beginCapture(id);assert(reused);assert(rows(owner).size()==3);
    assert(rows(owner).at(2).toMap().value("birth")!=birth);
    owner.cancelCapture(id);reused.reset();queued();
    assert(rows(owner).size()==3);assert(!rows(owner).at(2).toMap().value("alive").toBool());
    auto request=command();assert(!owner.featureSnapshotCaptureOriginals(request).isEmpty());
    assert(owner.featureSnapshotCaptureOriginals(request).isEmpty());
    QTemporaryDir directory;assert(directory.isValid());
    TestScriptingInterface test;test._testResultsLocation=directory.path();
    overte::e2e::FeatureLifecycle lifecycle(&test);assert(lifecycle.start(directory.path()));test._featureLifecycle=&lifecycle;
    auto query=command("arm");query.insert("action","feature-snapshot-capture-originals");
    assert(test.featureSnapshotCaptureOriginals(query).isEmpty()); // No dependency, no creation.
    DependencyManager::original=QSharedPointer<Snapshot>::create();
#if defined(ANDROID_APP_PICO_INTERFACE)
    qApp->hmd=false;assert(test.featureSnapshotCaptureOriginals(query).isEmpty());qApp->hmd=true;
    auto invalid=query;invalid.insert("expected","complete");assert(test.featureSnapshotCaptureOriginals(invalid).isEmpty());
    // Original dispatch queue stays bounded and its late arm is discarded.
    QElapsedTimer elapsed;elapsed.start();QVariantMap unavailable;
    std::thread script([&]{unavailable=test.featureSnapshotCaptureOriginals(query);});script.join();
    assert(unavailable.isEmpty() && elapsed.elapsed()<1800);
    assert(test.featureSnapshotCaptureOriginals(query).isEmpty()); // Unretired original queued callback.
    queued();const auto actual=test.featureSnapshotCaptureOriginals(query);
    assert(!actual.isEmpty());assert(actual.value("requests").toList().isEmpty());
#else
    assert(test.featureSnapshotCaptureOriginals(query).isEmpty());
#endif
    DependencyManager::original.reset();

}
