// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QCoreApplication>
#include <QGuiApplication>
#include <QWindow>
#include <QElapsedTimer>
#include <QSemaphore>
#include <QVariantMap>
#include <QSet>
#include <QSharedPointer>
#include <QJsonObject>
#include <vector>
#include <RequestCancellation.h>
#include <limits>
#include <QTemporaryDir>
#include <QFile>
#include <QBuffer>
#include <QNetworkRequest>
#include <QHttpMultiPart>
#include <QNetworkAccessManager>
#include <QJsonDocument>
#include <cassert>
#include <cstring>
#include <cstdio>
#include <fcntl.h>
#include "libraries/networking/src/PicoSnapshotUploadEvidence.h"
#include "original-callback-params.inc"
#include "original-callback-constructor.inc"
class AccountManager : public QObject {
public:
    struct Row {QString path;AccountManagerAuth::Type auth;QNetworkAccessManager::Operation operation;JSONCallbackParameters callbacks;QByteArray body;};
    std::vector<Row> rows;
    void sendRequest(const QString& path,AccountManagerAuth::Type auth,QNetworkAccessManager::Operation operation,
            const JSONCallbackParameters& callbacks,const QByteArray& body={},QHttpMultiPart* =nullptr,const QVariantMap& ={}) {
        rows.push_back({path,auth,operation,callbacks,body});
    }
};
class WindowScriptingInterface : public QObject {public:void snapshotShared(bool,const QString&) {}};
class DependencyManager {
public:template<class T> static QSharedPointer<T> get() {static auto value=QSharedPointer<T>::create();return value;}
};
#include "interface/src/ui/SnapshotUploader.cpp"
#include "original-snapshot-uploader.moc"

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "tests/device/native/AudioSettingsQueue.h"
#include "tests/device/native/FeatureLifecycle.h"
#include "tests/device/native/PrivatePreviewFiles.h"
using overte::e2e::PicoSnapshotUploadEvidence;
static void actualAccountUploadHook(const JSONCallbackParameters& callbackParams,QNetworkReply* networkReply,
        const QNetworkRequest& networkRequest,AccountManagerAuth::Type authType,const QByteArray& dataByteArray,QHttpMultiPart* dataMultiPart) {
#include "original-account-upload-hook.inc"
}

class HostApplication : public QGuiApplication {
public:using QGuiApplication::QGuiApplication;bool isHMDMode() const {return hmd;}bool hmd{true};
};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
class TestScriptingInterface : public QObject {
public:
    QVariantMap featurePicoSnapshotUpload(const QVariantMap&);
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    overte::e2e::FeatureLifecycle* _featureLifecycle{nullptr};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QSet<QString> _featureSnapshotUploadQueries;quint64 _featureSnapshotUploadSequence{0};
};

class Reply : public QNetworkReply {
public:
    explicit Reply(QByteArray original="{\"original\":true}"):body(original) {
        setOperation(QNetworkAccessManager::PostOperation);setUrl(QUrl("https://fixture.invalid/api/v1/snapshots"));
        setRawHeader("X-Overte-Fixture-Response",QByteArray(32,'c'));setAttribute(QNetworkRequest::HttpStatusCodeAttribute,200);
        open(QIODevice::ReadOnly|QIODevice::Unbuffered);
    }
    void abort() override {}
    bool isSequential() const override {return true;}
    qint64 bytesAvailable() const override {return body.size()-position+QNetworkReply::bytesAvailable();}
    void complete() {setFinished(true);emit uploadProgress(3,3);emit finished();}
protected:
    qint64 readData(char* output,qint64 size) override {
        const auto bytes=qMin<qint64>(size,body.size()-position);if(bytes<=0) {return -1;}
        std::memcpy(output,body.constData()+position,bytes);position+=bytes;return bytes;
    }
private:QByteArray body;qint64 position{0};
};
static QVariantMap onlyJob() {const auto value=PicoSnapshotUploadEvidence::get().snapshot();assert(value.value("complete").toBool());
    const auto jobs=value.value("jobs").toList();assert(jobs.size()==1);return jobs[0].toMap();}
#else
using HostApplication=QGuiApplication;
class TestScriptingInterface : public QObject {public:QVariantMap featurePicoSnapshotUpload(const QVariantMap&);};
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "original-snapshot-upload-getter.inc"
#endif
int main(int argc,char** argv) {
    HostApplication application(argc,argv);
#if defined(OVERTE_E2E_FEATURE_TESTS) && !defined(ANDROID_APP_PICO_INTERFACE)
    assert(TestScriptingInterface().featurePicoSnapshotUpload({}).isEmpty());
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    auto& evidence=PicoSnapshotUploadEvidence::get();const bool enabled=application.arguments().contains("--testScript");
    QTemporaryDir directory;assert(directory.isValid());const auto path=directory.path()+"/original.png";
    QObject* uploader=new QObject;const auto id=evidence.begin(uploader,path,QUrl("hifi://original/place"));
    if(!enabled) {assert(id.isEmpty() && evidence.snapshot().isEmpty());delete uploader;return 0;}
    assert(id.size()==32);
    {QFile original(path);assert(original.open(QIODevice::WriteOnly));assert(original.setPermissions(QFile::ReadOwner|QFile::WriteOwner));assert(original.write("abc",3)==3);}
    auto* file=new overte::e2e::PicoSnapshotUploadFile(path,id);assert(file->open(QIODevice::ReadOnly));evidence.file(id,file);
    auto row=onlyJob();auto original=row.value("file").toMap();assert(original.value("bytes").toInt()==3 && original.value("mode").toUInt()==0100600);
    assert(original.value("links").toInt()==1 && row.value("fileAlive").toBool());
    assert(file->readAll()=="abc");row=onlyJob();original=row.value("file").toMap();
    assert(original.value("readBytes").toInt()==3 && original.value("readSha256")==original.value("sha256"));
    const int descriptor=file->handle();auto* multipart=new QHttpMultiPart(QHttpMultiPart::FormDataType);file->setParent(multipart);evidence.multipart(id,multipart);
    auto* reply=new Reply;QNetworkRequest request(QUrl("https://fixture.invalid/api/v1/snapshots"));request.setRawHeader("Authorization","Bearer synthetic-host-only");
    JSONCallbackParameters callbacks;callbacks.picoSnapshotUploadJob=id;callbacks.picoSnapshotUploadStage="image";
    actualAccountUploadHook(callbacks,reply,request,AccountManagerAuth::Required,{},multipart);reply->complete();
    row=onlyJob();const auto requests=row.value("requests").toList();assert(requests.size()==1);
    auto observed=requests[0].toMap();assert(observed.value("finished").toBool() && observed.value("status").toInt()==200);
    assert(observed.value("replyBytes").toInt()==17 && reply->readAll()=="{\"original\":true}");
    evidence.change(id,"terminal","success","terminal");delete reply;assert(onlyJob().value("requests").toList()[0].toMap().value("destroyed").toBool());
    file->close();assert(onlyJob().value("fileAlive").toBool());
    delete multipart;assert(::fcntl(descriptor,F_GETFD)==-1);row=onlyJob();assert(!row.value("fileAlive").toBool() && !row.value("multipartAlive").toBool());
    delete uploader;assert(!onlyJob().value("uploaderAlive").toBool());
    const QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","feature-pico-snapshot-upload"},{"runId",QString(32,'b')}};
    quint64 sequence=0;const auto value=overte::e2e::picoSnapshotUploadObservation(command,QString(32,'d'),sequence);
    assert(value.value("requestId")==command.value("commandId") && value.value("source").toMap().value("snapshotUploadObservationVersion").toInt()==2 && sequence==1);
    auto bad=command;bad["expectedUploaded"]=true;assert(overte::e2e::picoSnapshotUploadObservation(bad,QString(32,'d'),sequence).isEmpty() && sequence==1);
    QWindow window;window.show();window.requestActivate();QCoreApplication::processEvents();
    assert(QGuiApplication::applicationState()==Qt::ApplicationActive);
    QTemporaryDir privateState;assert(privateState.isValid());overte::e2e::FeatureLifecycle lifecycle(qApp);assert(lifecycle.start(privateState.path()));
    TestScriptingInterface source;source._testResultsLocation=privateState.path();source._featureLifecycle=&lifecycle;
    auto good=command;good["commandId"]=QString(32,'5');auto observedSource=source.featurePicoSnapshotUpload(good);
    assert(!observedSource.isEmpty() && observedSource.value("source").toMap().value("snapshotUploadObservationVersion").toInt()==2);
    assert(source.featurePicoSnapshotUpload(good).isEmpty());const auto consumed=source._featureSnapshotUploadQueries.size();
    auto badGetter=good;badGetter["commandId"]=QString(32,'6');badGetter["expectedUploaded"]=true;
    assert(source.featurePicoSnapshotUpload(badGetter).isEmpty() && source._featureSnapshotUploadQueries.size()==consumed);
    qApp->hmd=false;good["commandId"]=QString(32,'7');assert(source.featurePicoSnapshotUpload(good).isEmpty());qApp->hmd=true;
    QThread worker;worker.start();QSemaphore entered,release,back;source.moveToThread(&worker);
    QMetaObject::invokeMethod(&source,[&]{entered.release();release.acquire();},Qt::QueuedConnection);assert(entered.tryAcquire(1,1000));
    QElapsedTimer elapsed;elapsed.start();assert(source.featurePicoSnapshotUpload(good).isEmpty() && elapsed.elapsed()>=950 && elapsed.elapsed()<1500);
    assert(!source._featureSnapshotQueue->settled() && source._featureSnapshotUploadQueries.size()==consumed);
    release.release();QMetaObject::invokeMethod(&source,[&]{source.moveToThread(qApp->thread());back.release();},Qt::QueuedConnection);
    assert(back.tryAcquire(1,2000));worker.quit();assert(worker.wait(1000));assert(source._featureSnapshotQueue->settled());
    assert(source._featureSnapshotUploadQueries.size()==consumed); // late callback did not publish a source.
    const auto raw=QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);assert(::fwrite(raw.constData(),1,static_cast<size_t>(raw.size()),stdout)==static_cast<size_t>(raw.size()));
    // Actual complete original uploader TU; AccountManager/window and reply
    // data are explicit host seams. No request or successful wire is invented.
    auto account=DependencyManager::get<AccountManager>();bool terminal=false;auto* originalUploader=new SnapshotUploader(QUrl("hifi://actual/place"),path);
    const auto uploadJob=originalUploader->featurePicoUploadJob();assert(!uploadJob.isEmpty());
    QObject::connect(originalUploader,&SnapshotUploader::finished,[&](const QString& actual,const QString& state,const QString& error) {
        assert(actual==path && state=="success" && error.isEmpty());terminal=true;
    });
    Reply imageReply("{\"data\":{\"thumbnail_url\":\"https://fixture.invalid/thumb\",\"image_url\":\"https://fixture.invalid/image\",\"id\":\"7\",\"original_image_file_name\":\"original.png\"}}");
    originalUploader->uploadSuccess(&imageReply);assert(account->rows.size()==1);const auto& actualStory=account->rows[0];
    assert(actualStory.path=="/api/v1/user_stories" && actualStory.auth==AccountManagerAuth::Required && actualStory.operation==QNetworkAccessManager::PostOperation);
    assert(actualStory.callbacks.picoSnapshotUploadJob==uploadJob && actualStory.callbacks.picoSnapshotUploadStage=="story" && actualStory.callbacks.requestTicket.current());
    const auto story=QJsonDocument::fromJson(actualStory.body).object().value("user_story").toObject();assert(story.value("action")=="snapshot" && story.value("path")=="/place");
    Reply storyReply("{\"user_story\":{\"id\":42,\"details\":{\"image_url\":\"https://fixture.invalid/image\"}}}");
    originalUploader->createStorySuccess(&storyReply);assert(terminal);
    QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    auto* cancelled=new SnapshotUploader(QUrl("hifi://actual/place"),path);bool cancelledOnce=false;
    QObject::connect(cancelled,&SnapshotUploader::finished,[&](const QString&,const QString& state,const QString&){assert(state=="cancelled" && !cancelledOnce);cancelledOnce=true;});
    cancelled->cancel();cancelled->cancel();assert(cancelledOnce);QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    // An actual oversized original collection is unavailable, not retimed by
    // replaying its same command ID. These additional reply bodies are explicit
    // host signal seams; no uploaded image or backend result is qualified.
    for(int index=0;index<10;++index) {
        auto* retainedUploader=new QObject;const auto retained=evidence.begin(retainedUploader,path,QUrl("hifi://actual/place"));
        auto* retainedReply=new Reply(QByteArray(16000,'z'));
        evidence.request(retained,"image",retainedReply,request,true,{},nullptr,true);retainedReply->complete();delete retainedReply;delete retainedUploader;
    }
    assert(QJsonDocument::fromVariant(evidence.snapshot()).toJson(QJsonDocument::Compact).size()>200000);
    good["commandId"]=QString(32,'8');assert(source.featurePicoSnapshotUpload(good).isEmpty());
    assert(source._featureSnapshotUploadQueries.contains(good.value("commandId").toString()));
    const auto unavailableConsumed=source._featureSnapshotUploadQueries.size();assert(source.featurePicoSnapshotUpload(good).isEmpty());
    assert(source._featureSnapshotUploadQueries.size()==unavailableConsumed);
#endif
    return 0;
}
