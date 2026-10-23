"""Compile original Assets entity dispatch with explicit property/tree endpoints."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    stage=Path(stage);bodies={}
    def body(path,signature):
        text=original((ROOT/path).read_text(),signature);bodies[path+':'+signature]=text;return text
    def block(path,start,end):
        text=(ROOT/path).read_text();text=text[text.index(start):text.index(end,text.index(start))]
        bodies[path+':'+start]=text;return text
    api='libraries/entities/src/EntityScriptingInterface.cpp'
    tree='libraries/entities/src/EntityTree.cpp'
    props='libraries/entities/src/EntityItemProperties.cpp.in'
    types='libraries/entities/src/EntityTypes.cpp'
    header='libraries/entities/src/EntityTypes.h'
    enum=block(header,'    typedef enum EntityType_t {','    static bool typeIsValid')
    # Keep only the complete original enum; following declarations use product types.
    enum=enum[:enum.index('} EntityType;')+len('} EntityType;')]
    (stage/'AssetsEntityEnum.inc').write_text(enum)
    declarations=(ROOT/'libraries/entities/src/EntityScriptingInterface.h').read_text()
    inline=original(declarations,'Q_INVOKABLE QUuid addEntity(const EntityItemProperties& properties, bool avatarEntity');bodies['addEntity-inline']=inline
    (stage/'AssetsEntityInline.inc').write_text(inline.replace('Q_INVOKABLE ',''))
    parts=[body('libraries/shared/src/SharedUtil.cpp','quint64 usecTimestampNow('),block('libraries/shared/src/ShapeInfo.cpp','const char* shapeTypeNames[]','// Bullet'),
        body('libraries/shared/src/ShapeInfo.cpp','QString ShapeInfo::getNameForShapeType('),
        block(props,'inline void addShapeType(','QString EntityItemProperties::getShapeTypeAsString'),
        body(props,'void EntityItemProperties::setShapeTypeFromString(')]
    for signature in ('QVariantMap vec3ToQMap(','glm::vec3 qMapToVec3(','glm::quat qMapToQuat('):
        parts.append(body('libraries/shared/src/QVariantGLM.cpp',signature))
    for signature in ('glm::vec3 sum(','glm::vec3 multiply(float','glm::vec3 multiply(const glm::vec3&'):
        parts.append(body('libraries/script-engine/src/Vec3.h',signature).replace('glm::vec3 ','glm::vec3 Vec3::',1))
    for signature in ('glm::vec3 Vec3::fromPolar(const','glm::vec3 Vec3::fromPolar(float'):
        parts.append(body('libraries/script-engine/src/Vec3.cpp',signature))
    parts.append(body('libraries/script-engine/src/Quat.cpp','glm::vec3 Quat::getForward('))
    glm=(ROOT/'libraries/shared/src/GLMHelpers.cpp').read_text()
    for prefix_line in ('const vec3 Vectors::UNIT_NEG_Z','const vec3& Vectors::FRONT'):
        line=next(line for line in glm.splitlines() if line.startswith(prefix_line));bodies[prefix_line]=line;parts.insert(0,line)
    for signature in ('const QString GRABBABLE_USER_DATA','const QString NOT_GRABBABLE_USER_DATA'):
        line=next(line for line in (ROOT/api).read_text().splitlines() if line.startswith(signature));parts.append(line);bodies[signature]=line
    parts.extend(body(api,sig) for sig in ('EntityItemProperties convertPropertiesFromScriptSemantics(',
        'void synchronizeEditedGrabProperties(', 'QUuid EntityScriptingInterface::addEntityInternal(',
        'bool EntityScriptingInterface::addLocalEntityCopy(', 'QUuid EntityScriptingInterface::addModelEntity('))
    parts.extend(body(tree,sig) for sig in ('void convertGrabUserDataToProperties(',
        'EntityItemPointer EntityTree::addEntity('))
    parts.append(body('libraries/entities/src/EntityItem.cpp.in','void EntityItem::recordCreationTime('))
    parts.extend(body(types,sig) for sig in ('const QString& EntityTypes::getEntityTypeName(',
        'bool EntityTypes::registerEntityType(', 'EntityItemPointer EntityTypes::constructEntityItem('))
    clock_adjust=next(line for line in (ROOT/'libraries/shared/src/SharedUtil.cpp').read_text().splitlines() if 'usecTimestampNowAdjust =' in line)
    bodies['clock-adjust-default']=clock_adjust;parts.insert(0,clock_adjust)
    defaults=(ROOT/'libraries/entities/src/EntityItemPropertiesDefaults.h').read_text()
    constants='\n'.join(next(line for line in defaults.splitlines() if line.startswith(prefix)) for prefix in (
        'const glm::vec3 ENTITY_ITEM_ZERO_VEC3', 'const float ENTITY_ITEM_DEFAULT_WIDTH',
        'const glm::vec3 ENTITY_ITEM_DEFAULT_DIMENSIONS', 'const glm::vec3 ENTITY_ITEM_DEFAULT_POSITION',
        'const glm::vec3 ENTITY_ITEM_DEFAULT_GRAVITY', 'const bool ENTITY_ITEM_DEFAULT_DYNAMIC', 'const bool ENTITY_ITEM_DEFAULT_COLLISIONLESS'))
    bodies['property-defaults']=constants;(stage/'AssetsEntityDefaults.inc').write_text(constants+'\n')
    (stage/'AssetsEntityOriginals.inc').write_text('\n'.join(parts)+'\n')
    provenance={name:hashlib.sha256(text.encode()).hexdigest() for name,text in bodies.items()}
    provenance['entityEnumUsed']=hashlib.sha256(enum.encode()).hexdigest()
    (stage/'entity-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    output=stage/'entity-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),str(HERE/'assets-entity-host.h'),'-o',str(output)],check=True,timeout=20,env=environment)
    return ['-DASSETS_ORIGINAL_ENTITY_LINK',str(output)]
