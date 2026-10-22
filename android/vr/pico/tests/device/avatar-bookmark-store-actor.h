// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QTemporaryDir>
#include <QLoggingCategory>
#include <QUrl>
#include "tests/device/native/AvatarBookmarkStorage.h"
#include "tests/device/native/AvatarBookmarkLoads.h"
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
class MyAvatar:public QObject {Q_OBJECT
public:
    void useFullAvatarURL(const QUrl&,const QString& name=QString());
    QVariantMap e2eAvatarLoads(){return {{"instance",avatarBirthActor}};}
    QUuid getSessionUUID()const{return QUuid("77777777-7777-4777-8777-777777777777");}
    QUrl getSkeletonModelURL()const{return skeletonActor;}
    void setSkeletonModelURL(const QUrl& url){skeletonActor=url;++modelRequestsActor;}
    void clearWornAvatarEntities(){++clearsActor;}void setAvatarScale(float value){scaleActor=value;}
    QUrl _fullAvatarURLFromPreferences,skeletonActor;QString _fullAvatarModelName,avatarBirthActor{QUuid::createUuid().toString(QUuid::Id128)};
    int modelRequestsActor{0},clearsActor{0};float scaleActor{1};
signals:void onLoadComplete();
};
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
#include "actual-avatar-bookmark-store.inc"
#undef BLOCKING_INVOKE_METHOD
}
