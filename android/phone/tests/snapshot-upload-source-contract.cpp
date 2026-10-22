// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Snapshot/SnapshotUploader/AccountManager method bodies are inserted
// verbatim. Account state, DependencyManager and the UI entry are host fixtures;
// HTTP/TLS/multipart/file/cancellation and QObject lifetimes use actual Qt.
#include <QChar>
#include <QCoreApplication>
#include <QDebug>
#include <QEventLoop>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLoggingCategory>
#include <QRegularExpression>
#include <QSharedPointer>
#include <QSslCertificate>
#include <QSslConfiguration>
#include <QThread>
#include <QTimer>
#include <AccountFixture.h>
#include <PhoneSnapshotUploadEvidence.h>
#include <CredentialTransportPolicy.h>
#include "SnapshotUploader.h"
#include "scripting/WindowScriptingInterface.h"

Q_LOGGING_CATEGORY(networking,"overte.e2e.upload.contract")
constexpr bool VERBOSE_HTTP_REQUEST_DEBUGGING=false;
const QByteArray ACCESS_TOKEN_AUTHORIZATION_HEADER="Authorization";
const QByteArray METAVERSE_SESSION_ID_HEADER="HFM-SessionID";
namespace overte::security { enum class DiagnosticEvent { Redacted };inline QString diagnosticEvent(DiagnosticEvent) { return "redacted"; } }
class NetworkAccessManager {
public:static QNetworkAccessManager& getInstance() { static thread_local overte::network::CredentialNetworkAccessManager manager;return manager; }
};

// @ORIGINAL_ACCOUNT_SEND@

namespace overte::snapshot { inline QString exportPath(const QString& path) { return QFileInfo(path).isFile() ? path : QString(); } }
struct SnapshotMetaData { QUrl getURL() const { return {}; } };
struct SnapshotHistory { void record(const QString&,const QString&,const QString&,const QString&) {} };
class Snapshot : public QObject {
    Q_OBJECT
public:
    void uploadSnapshot(const QString&,const QUrl& = {});
    void cancelUpload(const QString&);
    void cancelUploads();
    bool nativeReviewEnabled() const { return true; }
    SnapshotMetaData* parseSnapshotData(const QString&) { return nullptr; }
    QHash<QString,QPointer<SnapshotUploader>> _uploads;
    bool _uploadContextConnected{false};SnapshotHistory _history;SnapshotHistory* _featureSnapshotHistory{&_history};
signals:void uploadStatusChanged(const QString&,const QString&,const QString&);
};

// @ORIGINAL_SNAPSHOT_UPLOAD@
// @ORIGINAL_SNAPSHOT_CANCEL@
// @ORIGINAL_SNAPSHOT_CANCEL_ALL@

static void check(bool value,const char* message) { if (!value) { qFatal("%s",message); } }

int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);check(argc==3,"Private original fixture configuration is required");
    QFile config(QString::fromLocal8Bit(argv[2]));check(config.open(QIODevice::ReadOnly),"Fixture configuration is unavailable");
    const auto settings=QJsonDocument::fromJson(config.readAll()).object();config.close();
    if (!QCoreApplication::arguments().contains("--testScript")) {
        check(overte::e2e::PhoneSnapshotUploadEvidence::get().snapshot().isEmpty(),"Non-test source became available");return 0;
    }
    quint64 observationSequence=0;QVariantMap request{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","phone-snapshot-upload-observe"},{"runId",QString(32,'b')}};
    const auto first=overte::e2e::phoneSnapshotUploadObservation(request,QString(32,'c'),observationSequence);
    check(first["requestId"]==request["commandId"] && observationSequence==1 && first["source"].toMap()["jobs"].toList().isEmpty(),"Original read-only entry is unavailable");
    request["expected"]="success";check(overte::e2e::phoneSnapshotUploadObservation(request,QString(32,'c'),observationSequence).isEmpty(),"Expected facts entered original command grammar");request.remove("expected");
    request["schemaVersion"]=true;check(overte::e2e::phoneSnapshotUploadObservation(request,QString(32,'c'),observationSequence).isEmpty(),"Boolean schema entered original command grammar");
    QFile certificate(settings["certificate"].toString());check(certificate.open(QIODevice::ReadOnly),"Test trust root is unavailable");
    auto ssl=QSslConfiguration::defaultConfiguration();ssl.setCaCertificates(QSslCertificate::fromData(certificate.readAll()));QSslConfiguration::setDefaultConfiguration(ssl);
    auto account=QSharedPointer<AccountManager>::create();account->endpoint=QUrl(settings["origin"].toString());account->token=settings["token"].toString().toUtf8();
    DependencyManager::value<AccountManager>()=account;
    auto window=QSharedPointer<WindowScriptingInterface>::create();DependencyManager::value<WindowScriptingInterface>()=window;
    qRegisterMetaType<AccountManagerAuth::Type>();qRegisterMetaType<JSONCallbackParameters>();qRegisterMetaType<QHttpMultiPart*>();qRegisterMetaType<QNetworkAccessManager::Operation>();
    QThread networkThread;account->moveToThread(&networkThread);networkThread.start();
    Snapshot snapshot;const auto path=settings["image"].toString();int signalCount=0;bool failure=false;
    QObject::connect(window.data(),&WindowScriptingInterface::snapshotShared,&app,[&](bool error,const QString&) { ++signalCount;failure=error; });
    const auto mode=settings["mode"].toString();snapshot.uploadSnapshot(path,QUrl("hifi://owned/1,2,3"));
    if (mode=="cancel") { QTimer::singleShot(60,&snapshot,[&] { snapshot.cancelUploads(); }); }
    QEventLoop loop;QTimer deadline;deadline.setSingleShot(true);QObject::connect(&deadline,&QTimer::timeout,&loop,&QEventLoop::quit);deadline.start(4500);
    QTimer poll;poll.setInterval(10);QObject::connect(&poll,&QTimer::timeout,&loop,[&] {
        const auto source=overte::e2e::PhoneSnapshotUploadEvidence::get().snapshot();const auto jobs=source["jobs"].toList();if (jobs.size()!=1) { return; }
        const auto job=jobs[0].toMap();if (job["uploaderAlive"].toBool() || job["fileAlive"].toBool() || job["multipartAlive"].toBool()) { return; }
        for (const auto& item:job["requests"].toList()) { const auto request=item.toMap();if (!request["finished"].toBool() || !request["destroyed"].toBool()) { return; } }
        loop.quit();
    });poll.start();loop.exec();poll.stop();check(deadline.isActive(),"Original native upload did not retire within its existing source bound");
    const auto source=overte::e2e::PhoneSnapshotUploadEvidence::get().snapshot();check(source["complete"].toBool(),"Original native history is incomplete");
    const auto job=source["jobs"].toList()[0].toMap();const auto requests=job["requests"].toList();
    check(!job["uploaderAlive"].toBool() && !job["fileAlive"].toBool() && !job["multipartAlive"].toBool(),"Original native lifetimes remain live");
    if (mode=="success") { check(signalCount==1 && !failure && job["terminal"]=="success" && requests.size()==2,"Actual image/story request chain did not succeed"); }
    else if (mode=="cancel") { check(signalCount==0 && job["cancelRequested"].toBool() && job["terminal"]=="cancelled","Cancelled callback escaped the original ticket gate"); }
    else { check(signalCount==1 && failure && job["terminal"]=="error" && requests.size()==(mode=="story-not-found" ? 2 : 1),"Actual transport error did not remain an error"); }
    QFile original(settings["output"].toString());check(original.open(QIODevice::WriteOnly|QIODevice::NewOnly),"Original source output already exists");original.setPermissions(QFile::ReadOwner|QFile::WriteOwner);original.write(QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact));original.close();
    QMetaObject::invokeMethod(account.data(),[&] { account->moveToThread(app.thread()); },Qt::BlockingQueuedConnection);networkThread.quit();networkThread.wait();
    qInfo("Actual Snapshot upload chain and original native lifetimes passed");return 0;
}
#include "contract.moc"
