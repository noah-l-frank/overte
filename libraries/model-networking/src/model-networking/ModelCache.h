//
//  ModelCache.h
//  libraries/model-networking
//
//  Created by Zach Pomerantz on 3/15/16.
//  Copyright 2016 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#ifndef hifi_ModelCache_h
#define hifi_ModelCache_h

#include <QtCore/QSharedPointer>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QUuid>
#include <QCryptographicHash>
#endif

#include <DependencyManager.h>
#include <ResourceCache.h>

#include <graphics/Asset.h>

#include "FBXSerializer.h"
#include <procedural/ProceduralMaterialCache.h>
#include <material-networking/TextureCache.h>
#include "ModelLoader.h"

class MeshPart;

using GeometryMappingPair = std::pair<QUrl, QVariantHash>;
Q_DECLARE_METATYPE(GeometryMappingPair)

class Geometry {
public:
    using Pointer = std::shared_ptr<Geometry>;
    using WeakPointer = std::weak_ptr<Geometry>;

    Geometry() = default;
    Geometry(const Geometry& geometry);
    virtual ~Geometry() = default;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    QString e2eGeometryInstance() const { return _e2eIdentity.value; }
    // Passive inspection of the actual render geometry's material resources.
    // This never resolves/loads a URL or refreshes a cached texture.
    QVariantMap e2eCreateTextures() const {
        QVariantList rows;bool complete=true;
        for (size_t index=0;index<_materials.size();++index) {
            const auto material=_materials[index];if (!material) { continue; }
            for (const auto& slot:material->getTextures()) {
                const auto texture=slot.second.texture;if (!texture) { continue; }
                if (rows.size()>=256) { return {{"complete",false},{"rows",rows}}; }
                // Resource QObject/GPU state belongs to its owner thread.
                // The renderer reads only this mutex-protected original copy.
                auto original=texture->e2eOriginalTextureObservation();
                complete=complete && original.value("complete").toBool();
                original.insert("material",int(index));original.insert("channel",int(slot.first));original.insert("name",slot.second.name);
                rows.append(original);
                auto after=texture->e2eOriginalTextureObservation();
                original.remove("material");original.remove("channel");original.remove("name");
                complete=complete && original==after;
            }
        }
        return {{"complete",complete},{"rows",rows}};
    }
#endif

    // Immutable over lifetime
    using GeometryMeshes = std::vector<std::shared_ptr<const graphics::Mesh>>;
    using GeometryMeshParts = std::vector<std::shared_ptr<const MeshPart>>;

    // Mutable, but must retain structure of vector
    using NetworkMaterials = std::vector<std::shared_ptr<NetworkMaterial>>;

    bool isHFMModelLoaded() const { return (bool)_hfmModel; }

    const HFMModel& getHFMModel() const { return *_hfmModel; }
    const HFMModel::ConstPointer& getConstHFMModelPointer() const { return _hfmModel; }
    const MaterialMapping& getMaterialMapping() const { return _materialMapping; }
    const GeometryMeshes& getMeshes() const { return *_meshes; }
    const std::shared_ptr<NetworkMaterial> getShapeMaterial(int shapeID) const;

    const QVariantMap getTextures() const;
    void setTextures(const QVariantMap& textureMap);

    virtual bool areTexturesLoaded() const;
    const QUrl& getAnimGraphOverrideUrl() const { return _animGraphOverrideUrl; }
    bool shouldWaitForWearables() const { return _waitForWearables; }
    const QVariantHash& getMapping() const { return _mapping; }

protected:
    // Shared across all geometries, constant throughout lifetime
    HFMModel::ConstPointer _hfmModel;
    MaterialMapping _materialMapping;
    std::shared_ptr<const GeometryMeshes> _meshes;
    std::shared_ptr<const GeometryMeshParts> _meshParts;

    // Copied to each geometry, mutable throughout lifetime via setTextures
    NetworkMaterials _materials;

    QUrl _animGraphOverrideUrl;
    QVariantHash _mapping;  // parsed contents of FST file.
    bool _waitForWearables { false };

private:
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // Copies represent different loaded/rendered geometry objects. Assignment
    // also changes provenance; the copied object's identity is never adopted.
    struct Identity {
        QString value {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
        Identity() = default;
        Identity(const Identity&) : Identity() {}
        Identity& operator=(const Identity&) { value = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); return *this; }
    } _e2eIdentity;
#endif
    mutable bool _areTexturesLoaded { false };
};

/// A geometry loaded from the network.
class GeometryResource : public Resource, public Geometry {
    Q_OBJECT
public:
    using Pointer = QSharedPointer<GeometryResource>;

    GeometryResource(const QUrl& url, const ModelLoader& modelLoader) : Resource(url), _modelLoader(modelLoader) {}
    GeometryResource(const GeometryResource& other);

    QString getType() const override { return "Geometry"; }

    virtual void deleter() override;

    virtual void downloadFinished(const QByteArray& data) override;
    void setExtra(void* extra) override;

    virtual bool areTexturesLoaded() const override { return isLoaded() && Geometry::areTexturesLoaded(); }

private slots:
    void onGeometryMappingLoaded(bool success);

protected:
    friend class ModelCache;

    Q_INVOKABLE void setGeometryDefinition(HFMModel::Pointer hfmModel, const MaterialMapping& materialMapping);

    // Geometries may not hold onto textures while cached - that is for the texture cache
    // Instead, these methods clear and reset textures from the geometry when caching/loading
    bool shouldSetTextures() const { return _hfmModel && _materials.empty(); }
    void setTextures();
    void resetTextures();

    virtual bool isCacheable() const override { return _loaded && _isCacheable; }

private:
    ModelLoader _modelLoader;
    GeometryMappingPair _mappingPair;
    QUrl _textureBaseURL;
    bool _combineParts;

    GeometryResource::Pointer _geometryResource;
    QMetaObject::Connection _connection;

    bool _isCacheable{ true };
};

class GeometryResourceWatcher : public QObject {
    Q_OBJECT
public:
    using Pointer = std::shared_ptr<GeometryResourceWatcher>;

    GeometryResourceWatcher() = delete;
    GeometryResourceWatcher(Geometry::Pointer& geometryPtr) : _geometryRef(geometryPtr) {}

    void setResource(GeometryResource::Pointer resource);

    QUrl getURL() const { return (bool)_resource ? _resource->getURL() : QUrl(); }
    int getResourceDownloadAttempts() { return _resource ? _resource->getDownloadAttempts() : 0; }
    int getResourceDownloadAttemptsRemaining() { return _resource ? _resource->getDownloadAttemptsRemaining() : 0; }

private:
    void startWatching();
    void stopWatching();

signals:
    void finished(bool success);

private slots:
    void resourceFinished(bool success);
    void resourceRefreshed();

private:
    GeometryResource::Pointer _resource;
    Geometry::Pointer& _geometryRef;
};

/// Stores cached model geometries.
class ModelCache : public ResourceCache, public Dependency {
    Q_OBJECT
    SINGLETON_DEPENDENCY

public:

    GeometryResource::Pointer getGeometryResource(const QUrl& url,
                                                  const GeometryMappingPair& mapping =
                                                        GeometryMappingPair(QUrl(), QVariantHash()),
                                                  const QUrl& textureBaseUrl = QUrl());

    GeometryResource::Pointer getCollisionGeometryResource(const QUrl& url,
                                                           const GeometryMappingPair& mapping =
                                                                 GeometryMappingPair(QUrl(), QVariantHash()),
                                                           const QUrl& textureBaseUrl = QUrl());

protected:
    friend class GeometryResource;

    virtual QSharedPointer<Resource> createResource(const QUrl& url) override;
    QSharedPointer<Resource> createResourceCopy(const QSharedPointer<Resource>& resource) override;

private:
    ModelCache();
    virtual ~ModelCache() = default;
    ModelLoader _modelLoader;
};

class MeshPart {
public:
    MeshPart(int mesh, int part, int material) : meshID { mesh }, partID { part }, materialID { material } {}
    int meshID { -1 };
    int partID { -1 };
    int materialID { -1 };
};

#endif // hifi_ModelCache_h
