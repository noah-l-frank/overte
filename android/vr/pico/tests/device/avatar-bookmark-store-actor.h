// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QTemporaryDir>
#include <QLoggingCategory>
#include "tests/device/native/AvatarBookmarkStorage.h"
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
class AvatarBookmarks:public Bookmarks {public:
    AvatarBookmarks();QVariantMap e2eBookmarkStorage()const;QVariantMap getBookmarkInternal(const QString&);QVariantMap getBookmarks();
    void addBookmarkInternal(const QString&);void removeBookmarkInternal(const QString&);
    QVariantMap getAvatarDataToBookmark(){return currentAvatarActor;}
    void bookmarkAdded(const QString&){}void bookmarkDeleted(const QString&){}
    QVariantMap currentAvatarActor;const QString AVATARBOOKMARKS_FILENAME="avatarbookmarks.json";
};
#define BLOCKING_INVOKE_METHOD(...) qFatal("Unexpected foreign-thread mutation in GUI bookmark actor")
#include "actual-avatar-bookmark-store.inc"
#undef BLOCKING_INVOKE_METHOD
}
