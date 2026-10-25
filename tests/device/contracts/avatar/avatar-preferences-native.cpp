// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/AvatarPreferenceSnapshot.h"
#include <SettingHandle.h>
#include <QTimer>
#include <QJsonDocument>
#include <QTextStream>
#include <QRegularExpression>
#include <QDebug>
#include <cmath>
#include <cassert>
#include <thread>
#include <vector>
#include <sys/stat.h>
#include "tests/device/native/PrivateScriptFiles.h"
struct ForeignPreferenceValue{int value{1};};
Q_DECLARE_METATYPE(ForeignPreferenceValue)
static int foreignPreferenceStreams=0;
QDataStream&operator<<(QDataStream&stream,const ForeignPreferenceValue&value){++foreignPreferenceStreams;return stream<<value.value;}
QDataStream&operator>>(QDataStream&stream,ForeignPreferenceValue&value){return stream>>value.value;}
// Explicit application/dependency-registry and native avatar/model live-value
// actors. The Handle declarations+initializer keys, complete passive methods,
// Manager/WriteWorker/Handle persistence and original JSON codec are real.
DependencyManager& DependencyManager::manager(){static auto* value=new DependencyManager;return *value;}
QSharedPointer<Dependency> DependencyManager::safeGet(size_t code)const{QMutexLocker lock(&_instanceHashMutex);return _instanceHash.value(code);}
Q_LOGGING_CATEGORY(settings_interface,"settings.interface")
Q_LOGGING_CATEGORY(settings_handle,"settings.handle")
namespace Setting {
#include "actual-setting-interface.inc"
}
struct Camera{float getSensitivity(){return 1;}};
struct HostApplication:QCoreApplication{using QCoreApplication::QCoreApplication;Camera&getCamera(){return camera;}Camera camera;};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
const QString SETTINGS_FULL_PRIVATE_GROUP_NAME="fullPrivate";
static const QString AVATAR_SETTINGS_GROUP_NAME="Avatar",DOMINANT_RIGHT_HAND="right",DEFAULT_HMD_AVATAR_ALIGNMENT_TYPE="head";
static const bool DEFAULT_STRAFE_ENABLED=true;static const float DEFAULT_AVATAR_HEIGHT=1.7f;
static const QString allowAvatarStandingPreferenceStrings[]={"default"},allowAvatarLeaningPreferenceStrings[]={"default"};
enum class AllowAvatarStandingPreference{Default};enum class AllowAvatarLeaningPreference{Default};
struct AvatarData{static QUrl defaultFullAvatarModelUrl(){return QUrl("qrc:/meshes/defaultAvatar_full.fst");}};
struct CachedFloat{float get()const{return 2;}};
struct Model:QObject{QString e2eModelInstance()const{return QString(32,'b');}};
class MyAvatar:public QObject {
public:
    MyAvatar();QVariantMap e2ePreferenceHandles()const;
    QUuid getSessionUUID()const{return QUuid("11111111-1111-4111-8111-111111111111");}
    std::shared_ptr<Model>getSkeletonModel(){return model;}
    QUrl getFullAvatarURLFromPreferences()const{return AvatarData::defaultFullAvatarModelUrl();}
    QString getFullAvatarModelName()const{return _fullAvatarModelName;}
    float getModelScale()const{return 1;}float getTargetScale()const{return _targetScale;}
    QString getDominantHand()const{return "right";}QString getHmdAvatarAlignmentType()const{return "head";}
    bool getCollisionsEnabled(){return true;}bool getOtherAvatarsCollisionsEnabled(){return true;}
    QString getCollisionSoundURL(){return _collisionSoundURL;}QUrl getAnimGraphOverrideUrl()const{return {};}
    std::shared_ptr<Model>model{new Model};float _targetScale{1},_yawSpeed{1},_hmdYawSpeed{1},_pitchSpeed{1};
    QString _fullAvatarModelName{"original"},_collisionSoundURL;bool _useSnapTurn{true},_hoverWhenUnsupported{true},_flyingPrefHMD{false};
    int _movementReference{0};CachedFloat _vrWalkSpeed;
#include "actual-avatar-handles.inc"
};
#include "actual-avatar-preferences.inc"
class AvatarManager:public Dependency{public:std::shared_ptr<MyAvatar>avatar{new MyAvatar};auto getMyAvatar(){return avatar;}};
struct Lifecycle{QVariantMap snapshot(){return {{"active",true}};}};
class TestScriptingInterface:public QObject {
public:
    QVariantMap featurePicoAvatarPreferences(const QVariantMap&command);
    QString _testResultsLocation{"private"},_featureObservationInstance{QString(32,'c')};
    std::shared_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
    std::shared_ptr<overte::e2e::AudioSettingsQueue>_featureAvatarPreferencesQueue{new overte::e2e::AudioSettingsQueue};
    std::shared_ptr<overte::e2e::AvatarPreferenceSnapshot>_featureAvatarPreferences{new overte::e2e::AvatarPreferenceSnapshot};
    QSet<QString>_featureAvatarPreferencesRequests;quint64 _featureAvatarPreferencesSequence{0};
    QPointer<QObject>_featureAvatarPreferenceObject;QString _featureAvatarPreferenceBirth;
};
#include "actual-getter.inc"
class SettingsTests {
public:
    static void flush(Setting::Manager* m){m->forceSave();QObject barrier;barrier.moveToThread(&m->_workerThread);assert(QMetaObject::invokeMethod(&barrier,[&]{barrier.moveToThread(qApp->thread());},Qt::BlockingQueuedConnection));}
    static void stop(Setting::Manager*m){m->terminateThread();assert(m->_workerThread.wait(2000));}
    static QPointer<Setting::WriteWorker>worker(Setting::Manager*m){return m->_featureBrowseWriteWorker;}
    static auto&barrier(Setting::Manager*m){return m->_featureAvatarPreferencesBarrier;}
    static void registerActual(Setting::Manager*m,Setting::Interface* handle){m->registerHandle(handle);}
    static void writerCache(Setting::Manager*m,const std::function<void(QSettings*)>&f){const auto w=m->_featureBrowseWriteWorker;assert(QMetaObject::invokeMethod(w,[=]{assert(w->_qSettings);f(w->_qSettings);},Qt::BlockingQueuedConnection));}
};
void output(const QString&kind,const QVariantMap&request,const QVariantMap&packet){assert(!packet.isEmpty());QTextStream(stdout)<<QJsonDocument::fromVariant(QVariantMap{{"kind",kind},{"request",request},{"packet",packet}}).toJson(QJsonDocument::Compact)<<'\n';}
int main(int argc,char**argv){
    HostApplication app(argc,argv);assert(argc>=2);::umask(0077);const QString root=QString::fromLocal8Bit(argv[1]);
    app.setOrganizationName("OwnedAvatarPreferencesHost");app.setApplicationName("settings");QSettings::setDefaultFormat(JSON_FORMAT);QSettings::setPath(JSON_FORMAT,QSettings::UserScope,root);
    TestScriptingInterface tsi;int nonce=0;auto request=[&]{return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++nonce,16).rightJustified(32,'0')},{"action","feature-pico-avatar-preferences-observe"}};};
    assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(!DependencyManager::isSet<AvatarManager>());
    auto avatarManager=DependencyManager::set<AvatarManager>();auto avatar=avatarManager->avatar;
    assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(!DependencyManager::isSet<Setting::Manager>());
    auto manager=DependencyManager::set<Setting::Manager>();manager->setValue("unrelated",QByteArray("untouched"));SettingsTests::flush(manager.data());
    if(!app.arguments().contains("--testScript")){assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());avatarManager->avatar.reset();avatar.reset();SettingsTests::stop(manager.data());return 0;}
#if QT_VERSION < QT_VERSION_CHECK(6,0,0)
    qRegisterMetaTypeStreamOperators<ForeignPreferenceValue>();
#endif
    const auto foreignVariant=QVariant::fromValue(ForeignPreferenceValue{});
    assert(overte::e2e::avatarPreferenceRaw(true,foreignVariant).isEmpty());
    assert(overte::e2e::avatarPreferenceRaw(true,QVariantMap{{"nested",foreignVariant}}).isEmpty());
    assert(foreignPreferenceStreams==0);
    QVariant nested="leaf";for(int depth=0;depth<10;++depth){nested=QVariantList{nested};}
    assert(overte::e2e::avatarPreferenceRaw(true,nested).isEmpty());
    assert(overte::e2e::avatarPreferenceRaw(true,QString(32769,'x')).isEmpty());
    assert(avatar->_scaleSetting.e2ePreferenceSnapshot().isEmpty());
    auto publish=[&](const QString&kind){auto command=request();auto value=tsi.featurePicoAvatarPreferences(command);output(kind,command,value);assert(tsi.featurePicoAvatarPreferences(command).isEmpty());return value.value("source").toMap().value("snapshot").toMap();};
    const auto initial=publish("lazy-original");assert(!manager->contains("Avatar/scale"));
    auto& typedOwner=*tsi._featureAvatarPreferences;
    auto typedHandles=[&]{return QVariantMap{{"handles",avatar->e2ePreferenceHandles()}};};
    auto lazy=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(lazy.valid());
    auto lazyFailedIntent=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(lazyFailedIntent.valid());
    auto handles=initial.value("cache").toMap().value("native").toMap().value("handles").toMap().value("handles").toMap();
    assert(handles.size()==23 && !handles.value("scale").toMap().value("initialized").toBool());assert(handles.value("headPitch").toMap().value("key")==QVariant("Avatar/"));
    // A real get() mutates lazy initialization and inserts an invalid cache row.
    assert(avatar->_scaleSetting.get()==1);assert(manager->contains("Avatar/scale"));const auto initialized=publish("initialized-absent");
    assert(initialized.value("mutationSequence").toLongLong()>initial.value("mutationSequence").toLongLong());assert(initialized.value("cacheMatchesWriter")==QVariant(true));
    const auto initializedMemento=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(initializedMemento.valid());
    int journalSequence=0;auto durable=[&](const QVariantMap& event){
        const auto path=QDir(root).filePath(QString("lazy-cas-%1.json").arg(++journalSequence));
        QFile original(path);assert(original.open(QIODevice::WriteOnly|QIODevice::NewOnly));
        assert(original.setPermissions(QFile::ReadOwner|QFile::WriteOwner));
        const auto bytes=QJsonDocument::fromVariant(event).toJson(QJsonDocument::Compact);
        assert(original.write(bytes)==bytes.size() && original.flush() && ::fsync(original.handle())==0);original.close();
        const int directory=::open(QFile::encodeName(root).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        assert(directory>=0 && ::fsync(directory)==0);::close(directory);return true;
    };
    QThread::msleep(1501);
    assert(typedOwner.restoreUnwrittenLazy(lazy,initializedMemento,typedHandles,durable).isEmpty());assert(journalSequence==0);
    const auto initializedFresh=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(initializedFresh.valid());
    // Counter only: actual get() above initialized a lazy Handle without a
    // Settings write. This is not a fabricated Favorite preference effect.
    auto foreignBefore=lazy;Setting::Handle<float> foreignHandle("Avatar/scale",1);
    SettingsTests::registerActual(manager.data(),&foreignHandle);
    assert(typedOwner.restoreUnwrittenLazy(foreignBefore,initializedFresh,typedHandles,durable).isEmpty());
    assert(journalSequence==0 && avatar->_scaleSetting.e2ePreferenceSnapshot().isEmpty());
    SettingsTests::registerActual(manager.data(),&avatar->_scaleSetting);
    const auto afterForeign=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(afterForeign.valid());
    auto failedIntent=lazyFailedIntent;assert(typedOwner.restoreUnwrittenLazy(failedIntent,afterForeign,typedHandles,[](const QVariantMap&){return false;}).isEmpty());
    assert(typedOwner.restoreUnwrittenLazy(failedIntent,afterForeign,typedHandles,durable).isEmpty());assert(journalSequence==0);
    assert(typedOwner.restoreUnwrittenLazy(lazyFailedIntent,afterForeign,typedHandles,durable).isEmpty());
    const auto lazyResult=typedOwner.restoreUnwrittenLazy(lazy,afterForeign,typedHandles,durable);
    assert(lazyResult.value("verified")==QVariant(true) && journalSequence==2);
    assert(!manager->contains("Avatar/scale"));
    const auto restored=publish("lazy-cas-restored");
    assert(restored.value("mutationSequence").toLongLong()>initialized.value("mutationSequence").toLongLong());
    assert(typedOwner.restoreUnwrittenLazy(lazy,afterForeign,typedHandles,durable).isEmpty());assert(journalSequence==2);
    auto lostResultOriginal=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(lostResultOriginal.valid());
    assert(avatar->_scaleSetting.get()==1);
    const auto lostExpected=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(lostExpected.valid());
    assert(typedOwner.restoreUnwrittenLazy(lostResultOriginal,lostExpected,typedHandles,[&](const QVariantMap& event){
        durable(event);return event.value("phase")!=QVariant("result");
    }).isEmpty());assert(journalSequence==4 && !manager->contains("Avatar/scale"));
    assert(typedOwner.restoreUnwrittenLazy(lostResultOriginal,lostExpected,typedHandles,durable).isEmpty());assert(journalSequence==4);
    const auto resultLost=publish("lazy-cas-result-lost-restored");assert(resultLost.value("mutationSequence").toLongLong()>restored.value("mutationSequence").toLongLong());
    auto beforeSave=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(beforeSave.valid());
    avatar->_scaleSetting.set(1.5f);SettingsTests::flush(manager.data());const auto changed=publish("saved-scale");assert(changed.value("writer").toMap().value("matchesPhysical")==QVariant(true) && changed.value("cacheMatchesWriter")==QVariant(true));
    const auto written=typedOwner.remember(avatar.get(),avatar->_scaleSetting,typedHandles);assert(written.valid());
    assert(typedOwner.restoreUnwrittenLazy(beforeSave,written,typedHandles,durable).isEmpty());assert(journalSequence==4);
    // A dirty original writer can be ahead of real bytes; observing never syncs.
    SettingsTests::writerCache(manager.data(),[](QSettings*s){
        s->setValue("Avatar/scale",2.5f);
        const auto physical=overte::e2e::avatarPreferenceFile(s->fileName(),s->format());
        assert(!physical.isEmpty());assert(physical.value("rows").toMap()!=overte::e2e::avatarPreferenceEncoded({{"Avatar/scale",s->value("Avatar/scale")}}));
    });
    const auto dirty=publish("writer-only-conflict");assert(dirty.value("cacheMatchesWriter")==QVariant(false));
    SettingsTests::writerCache(manager.data(),[](QSettings*s){s->setValue("Avatar/scale",1.5f);s->sync();});
    QFile file(manager->fileName());assert(file.open(QIODevice::ReadOnly));const auto original=file.readAll();file.close();
    auto object=QJsonDocument::fromJson(original).object();object.insert("Avatar/scale",7.0);const auto foreign=QJsonDocument(object).toJson(QJsonDocument::Indented);
    assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(file.write(foreign)==foreign.size());file.close();
    const auto external=publish("physical-conflict");assert(external.value("writer").toMap().value("matchesPhysical")==QVariant(false));assert(external.value("mutationSequence")==changed.value("mutationSequence"));
    assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(file.write(original)==original.size());file.close();
    // Original QSettings normalizes trailing-slash headPitch to physical Avatar.
    avatar->_headPitchSetting.set(0.25f);SettingsTests::flush(manager.data());const auto alias=publish("head-pitch-original-key");
    assert(alias.value("cache").toMap().value("rows").toMap().contains("Avatar/"));assert(alias.value("writer").toMap().value("rows").toMap().contains("Avatar"));
    assert(alias.value("writer").toMap().value("matchesPhysical")==QVariant(true));
    // Physical bytes remain independently bounded and canonical. The fixture
    // restores only its own exact raw bytes, outside the product observer.
    assert(file.open(QIODevice::ReadOnly));const auto aliasBytes=file.readAll();file.close();
    auto writeFixture=[&](const QByteArray&bytes){assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(file.write(bytes)==bytes.size());file.close();};
    writeFixture("{\n    \"Avatar/scale\": 1,\n    \"Avatar/scale\": 2\n}\n");assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());writeFixture(aliasBytes);
    assert(file.setPermissions(QFile::ReadOwner|QFile::WriteOwner|QFile::ReadOther));assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(file.setPermissions(QFile::ReadOwner|QFile::WriteOwner));
    const auto backup=manager->fileName()+"-owned-backup";assert(::link(QFile::encodeName(manager->fileName()).constData(),QFile::encodeName(backup).constData())==0);assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(QFile::remove(backup));
    assert(QFile::rename(manager->fileName(),backup));assert(::symlink(QFile::encodeName(backup).constData(),QFile::encodeName(manager->fileName()).constData())==0);assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(QFile::remove(manager->fileName()));assert(QFile::rename(backup,manager->fileName()));
    manager->setValue("Avatar/oversized-original",QByteArray(65537,'x'));SettingsTests::flush(manager.data());assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());manager->remove("Avatar/oversized-original");SettingsTests::flush(manager.data());
    // Real mutation during the unlocked writer half invalidates a whole sample.
    auto&barrier=SettingsTests::barrier(manager.data());assert(barrier.read([]{return QVariantMap{{"same",true}};},[&]{manager->setValue("//Avatar//scale/",4);return QVariantMap{{"writer",true}};}).isEmpty());
    assert(barrier.read([]{return QVariantMap{{"same",true}};},[]{QThread::msleep(1501);return QVariantMap{{"writer",true}};}).isEmpty());
    manager->remove("//Avatar//scale/");avatar->_scaleSetting.set(1.6f);SettingsTests::flush(manager.data());
    const auto worker=SettingsTests::worker(manager.data());QSemaphore entered,released;assert(QMetaObject::invokeMethod(worker,[&]{entered.release();released.acquire();},Qt::QueuedConnection));entered.acquire();
    QElapsedTimer elapsed;elapsed.start();assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());assert(elapsed.elapsed()<1000);
    assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());released.release();SettingsTests::flush(manager.data());publish("late-result-discarded");
    // The observer never changes unowned rows or retires the original collector.
    assert(manager->value("unrelated")==QVariant(QByteArray("untouched")));
    const auto oldBirth=tsi._featureAvatarPreferenceBirth;avatarManager->avatar.reset(new MyAvatar);avatar.reset();SettingsTests::flush(manager.data());publish("avatar-replacement");assert(oldBirth!=tsi._featureAvatarPreferenceBirth);
    while(tsi._featureAvatarPreferencesRequests.size()<512){assert(!tsi.featurePicoAvatarPreferences(request()).isEmpty());}assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());
    avatarManager->avatar.reset();SettingsTests::stop(manager.data());assert(tsi.featurePicoAvatarPreferences(request()).isEmpty());return 0;
}
