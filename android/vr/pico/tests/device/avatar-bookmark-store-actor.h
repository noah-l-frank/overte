// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QTemporaryDir>
#include <QLoggingCategory>
#include <QUrl>
#include <shared/ReadWriteLockable.h>
#include "tests/device/native/AvatarBookmarkStorage.h"
#include "tests/device/native/AvatarBookmarkLoads.h"
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
#include "actual-avatar-render-tags.inc"
#endif
namespace avatar_bookmark_host {
// Only the avatar-data and Script permission boundaries are declared actors.
// The original constructor/cache/Get/Add/Remove/physical writer bodies below
// execute over this owned profile. This is not loaded wearable/model evidence.
class PathUtils {public:inline static QString profile;
    static QString getAppDataPath(){return profile;}static QString resourcesPath(){return profile+"/resources/";}
};
inline const QLoggingCategory& interfaceapp(){static QLoggingCategory value("pico.avatar.bookmark.host");return value;}
class ScriptPermissions {public:enum class Permission{SCRIPT_PERMISSION_GET_AVATAR_URL};static bool isCurrentScriptAllowed(Permission){return true;}};
class Bookmarks:public QObject {public:
    void insert(const QString&,const QVariant&);void remove(const QString&);bool contains(const QString&)const;
    void readFromFile();void persistToFile();QVariantMap _bookmarks;QString _bookmarksFilename,_bookmarkError;
};
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
// Only the raw preference caller/persistence is original in this slice.
// These scene/base-Avatar/Skeleton inputs are declared actors, not HFM/Model
// getters offered as evidence of a loaded resource or rendering effect.
struct GeometryInputActor {
    QVariantMap mapping;const QVariantMap& getMapping()const{return mapping;}
    QUrl getAnimGraphOverrideUrl()const{return {};}
};
class SkeletonModel:public ::Model {Q_OBJECT
public:
    void setTagMask(uint8_t){}void setGroupCulled(bool){}void setVisibleInScene(bool,int){}
    void setCauterizeBoneSet(const QSet<int>&){}
    std::shared_ptr<GeometryInputActor> getGeometry(){return geometry;}
    int actualConnections()const{return receivers(SIGNAL(skeletonLoaded()));}
    std::shared_ptr<GeometryInputActor> geometry{new GeometryInputActor};
signals:void skeletonLoaded();
};
class Avatar:public QObject,public ::AvatarData {
public:
    // The original base Avatar and Model::setURL are still an explicit seam.
    void setSkeletonModelURL(const QUrl& value){_skeletonModelURL=value;++modelRequestsActor;}
    QUrl _skeletonModelURL;int modelRequestsActor{0};
    std::shared_ptr<SkeletonModel> _skeletonModel{new SkeletonModel};
};
class MyAvatar:public Avatar {Q_OBJECT
public:
    MyAvatar();QVariantMap e2ePreferenceHandles()const;
    void useFullAvatarURL(const QUrl&,const QString& name=QString());
    QVariantMap e2eAvatarLoads(){return {{"instance",avatarBirthActor}};}
    QUuid getSessionUUID()const{return QUuid("77777777-7777-4777-8777-777777777777");}
    QUrl getSkeletonModelURL()const{return _skeletonModelURL;}
    void setSkeletonModelURL(const QUrl&);void saveAvatarUrl();QVariantMap e2eModelConnections()const;
    std::shared_ptr<overte::e2e::AvatarModelConnections> _featureModelConnections;
    void completeDeclaredModel(){assert(_skeletonModel->actualConnections()==1);emit _skeletonModel->skeletonLoaded();assert(_skeletonModel->actualConnections()==0);emit onLoadComplete();}
    void clearWornAvatarEntities();void setAvatarScale(float);
    void removeWornAvatarEntity(const QUuid&){qFatal("Nonempty wearable removal crosses the declared EntityTree boundary");}
    mutable ReadWriteLockable _avatarEntitiesLock;QMap<QUuid,QByteArray> _packedAvatarEntityData;
    QUrl _fullAvatarURLFromPreferences;QUrl& skeletonActor{_skeletonModelURL};QString _fullAvatarModelName,avatarBirthActor{QUuid::createUuid().toString(QUuid::Id128)};
    std::shared_ptr<::Model> getSkeletonModel(){return _skeletonModel;}
    QUrl getFullAvatarURLFromPreferences()const{return _fullAvatarURLFromPreferences;}
    QString getFullAvatarModelName()const{return _fullAvatarModelName;}
    float getModelScale()const{return _targetScale;}float getTargetScale()const{return _targetScale;}
    QString getDominantHand()const{return "right";}QString getHmdAvatarAlignmentType()const{return "head";}
    bool getCollisionsEnabled(){return true;}bool getOtherAvatarsCollisionsEnabled(){return true;}
    QString getCollisionSoundURL(){return _collisionSoundURL;}QUrl getAnimGraphOverrideUrl()const{return {};}
    int _skeletonModelChangeCount{0};QSet<int> _headBoneSet;bool _cauterizationNeedsUpdate{false};QUrl _fstAnimGraphOverrideUrl;
    void initHeadBones(){}void initAnimGraph(){}void initFlowFromFST(){}
    float _yawSpeed{1},_hmdYawSpeed{1},_pitchSpeed{1};
    QString _collisionSoundURL;bool _useSnapTurn{true},_hoverWhenUnsupported{true},_flyingPrefHMD{false};
    int _movementReference{0};CachedFloat _vrWalkSpeed;
#include "actual-avatar-handles.inc"
signals:void onLoadComplete();void skeletonChanged();
};
#else
class MyAvatar:public QObject,public ::AvatarData {Q_OBJECT
public:
    MyAvatar();QVariantMap e2ePreferenceHandles()const;
    void useFullAvatarURL(const QUrl&,const QString& name=QString());
    void completeDeclaredModel(){emit onLoadComplete();}
    QVariantMap e2eAvatarLoads(){return {{"instance",avatarBirthActor}};}
    QUuid getSessionUUID()const{return QUuid("77777777-7777-4777-8777-777777777777");}
    QUrl getSkeletonModelURL()const{return skeletonActor;}
    void setSkeletonModelURL(const QUrl& url){skeletonActor=url;++modelRequestsActor;}
    void clearWornAvatarEntities();void setAvatarScale(float);
    void removeWornAvatarEntity(const QUuid&){qFatal("Nonempty wearable removal crosses the declared EntityTree boundary");}
    mutable ReadWriteLockable _avatarEntitiesLock;QMap<QUuid,QByteArray> _packedAvatarEntityData;
    QUrl _fullAvatarURLFromPreferences,skeletonActor;QString _fullAvatarModelName,avatarBirthActor{QUuid::createUuid().toString(QUuid::Id128)};
    std::shared_ptr<::Model> getSkeletonModel(){return modelActor;}
    QUrl getFullAvatarURLFromPreferences()const{return _fullAvatarURLFromPreferences;}
    QString getFullAvatarModelName()const{return _fullAvatarModelName;}
    float getModelScale()const{return _targetScale;}float getTargetScale()const{return _targetScale;}
    QString getDominantHand()const{return "right";}QString getHmdAvatarAlignmentType()const{return "head";}
    bool getCollisionsEnabled(){return true;}bool getOtherAvatarsCollisionsEnabled(){return true;}
    QString getCollisionSoundURL(){return _collisionSoundURL;}QUrl getAnimGraphOverrideUrl()const{return {};}
    std::shared_ptr<::Model> modelActor{new ::Model};
    int modelRequestsActor{0};float _yawSpeed{1},_hmdYawSpeed{1},_pitchSpeed{1};
    QString _collisionSoundURL;bool _useSnapTurn{true},_hoverWhenUnsupported{true},_flyingPrefHMD{false};
    int _movementReference{0};CachedFloat _vrWalkSpeed;
#include "actual-avatar-handles.inc"
signals:void onLoadComplete();
};
#endif
class AvatarManager {public:std::shared_ptr<MyAvatar> avatar{std::make_shared<MyAvatar>()};std::shared_ptr<MyAvatar>getMyAvatar(){return avatar;}};
using EntityTreePointer=std::shared_ptr<int>;
class EntityTreeRenderer {public:EntityTreePointer getTree(){return {};}};
class DependencyManager {public:template<class T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}};
class UserActivityLogger {public:static UserActivityLogger&getInstance(){static UserActivityLogger value;return value;}void changedModel(const QString&,const QString&){++callsActor;}int callsActor{0};};
inline QVariantList entitiesActor;inline int additionsActor=0;
inline void addAvatarEntities(const QVariantList& entities){entitiesActor=entities;++additionsActor;}
class AvatarBookmarks:public Bookmarks {Q_OBJECT
public:
    AvatarBookmarks();QVariantMap e2eBookmarkStorage()const;QVariantMap e2eBookmarkLoads()const;QVariantMap getBookmarkInternal(const QString&);QVariantMap getBookmarks();
    void addBookmarkInternal(const QString&);void removeBookmarkInternal(const QString&);void loadBookmark(const QString&);void loadBookmarkInternal(const QString&);
    QVariantMap getAvatarDataToBookmark(){return currentAvatarActor;}
    QVariantMap currentAvatarActor;const QString AVATARBOOKMARKS_FILENAME="avatarbookmarks.json";
    const QString ENTRY_AVATAR_URL="avatarUrl",ENTRY_AVATAR_SCALE="avatarScale",ENTRY_AVATAR_ENTITIES="avatarEntites";
    overte::e2e::AvatarBookmarkLoads _featureBookmarkLoads;
signals:void bookmarkAdded(const QString&);void bookmarkDeleted(const QString&);void bookmarkLoaded(const QString&);
};
#define BLOCKING_INVOKE_METHOD(...) qFatal("Unexpected foreign-thread mutation in GUI bookmark actor")
#include "actual-avatar-preferences.inc"
#include "actual-avatar-bookmark-store.inc"
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
#include "actual-avatar-persistence.inc"
#endif
#undef BLOCKING_INVOKE_METHOD
}
