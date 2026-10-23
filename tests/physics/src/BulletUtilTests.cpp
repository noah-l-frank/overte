//
//  BulletUtilTests.cpp
//  tests/physics/src
//
//  Created by Andrew Meadows on 2014.11.02
//  Copyright 2014 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "BulletUtilTests.h"

#include <iostream>
#include <cmath>
#include <limits>

#include <BulletUtil.h>
#include <CharacterController.h>
#include <NumericalConstants.h>
#include <GLMHelpers.h>

// Add additional qtest functionality (the include order is important!)
#include <test-utils/QTestExtensions.h>

// Constants
const glm::vec3 origin(0.0f);
const glm::vec3 xAxis(1.0f, 0.0f, 0.0f);
const glm::vec3 yAxis(0.0f, 1.0f, 0.0f);
const glm::vec3 zAxis(0.0f, 0.0f, 1.0f);

namespace {

const CharacterController::FollowTimePerType NO_FOLLOW_TIME {};

class FloorProbeController final : public CharacterController {
public:
    FloorProbeController() : CharacterController(NO_FOLLOW_TIME) {
        auto shape = new btBoxShape(btVector3(0.2f, 1.0f, 0.2f));
        _rigidBody = new btRigidBody(btRigidBody::btRigidBodyConstructionInfo(1.0f, nullptr, shape));
    }

    void setProbe(const btVector3& origin, btScalar radius, const btVector3& up = btVector3(0, 1, 0)) {
        btTransform transform;
        transform.setIdentity();
        transform.setOrigin(origin);
        _rigidBody->setWorldTransform(transform);
        _radius = radius;
        _halfHeight = 1.0f;
        _currentUp = up;
        _floorDistance = FLT_MAX;
    }

    btScalar floorDistance() const { return _floorDistance; }
    void updateShapeIfNecessary() override {}
    int32_t computeCollisionMask() const override { return BULLET_COLLISION_MASK_MY_AVATAR; }
    void handleChangedCollisionMask() override {}

protected:
    void updateMassProperties() override {}
};

class FloorProbeWorld final : public btCollisionWorld {
public:
    using btCollisionWorld::btCollisionWorld;

    void rayTest(const btVector3& from, const btVector3& to, RayResultCallback& callback) const override {
        ++rayCalls;
        // Record invalid submissions without letting Bullet abort the host suite.
        // Valid probes below still use the real Bullet collision query.
        if (passRaysToBullet) {
            btCollisionWorld::rayTest(from, to, callback);
        }
    }

    mutable int rayCalls { 0 };
    bool passRaysToBullet { false };
};

} // namespace


QTEST_MAIN(BulletUtilTests)

void BulletUtilTests::characterFloorRaySafety() {
    btStaticPlaneShape floorShape(btVector3(0, 1, 0), 0);
    btCollisionObject floor;
    floor.setCollisionShape(&floorShape);
    btDefaultCollisionConfiguration configuration;
    btCollisionDispatcher dispatcher(&configuration);
    btDbvtBroadphase broadphase;
    FloorProbeWorld world(&dispatcher, &broadphase, &configuration);
    world.addCollisionObject(&floor);
    FloorProbeController controller;

    // A short ground probe collapses after rounding at a large finite origin.
    const btScalar farOrigin = std::ldexp(btScalar(1), std::numeric_limits<btScalar>::digits + 2);
    controller.setProbe(btVector3(0, farOrigin, 0), 0.2f);
    controller.preStep(&world);
    QCOMPARE(world.rayCalls, 0);
    QCOMPARE(controller.floorDistance(), btScalar(FLT_MAX));

    controller.setProbe(btVector3(0, 1, 0), btScalar(SIMD_EPSILON * 0.1));
    controller.preStep(&world);
    QCOMPARE(world.rayCalls, 0);

    controller.setProbe(btVector3(0, std::numeric_limits<btScalar>::infinity(), 0), 0.2f);
    controller.preStep(&world);
    QCOMPARE(world.rayCalls, 0);

    controller.setProbe(btVector3(0, 1, 0), 0.2f,
                        btVector3(std::numeric_limits<btScalar>::quiet_NaN(), 1, 0));
    controller.preStep(&world);
    QCOMPARE(world.rayCalls, 0);

    // Rejecting invalid probes must preserve actual nearby-floor detection.
    world.passRaysToBullet = true;
    controller.setProbe(btVector3(0, 1.15f, 0), 0.2f);
    controller.preStep(&world);
    QCOMPARE(world.rayCalls, 1);
    QVERIFY(std::fabs(controller.floorDistance() + 0.05f) < 0.00001f);
}

void BulletUtilTests::fromBulletToGLM() {
    btVector3 bV(1.23f, 4.56f, 7.89f);
    glm::vec3 gV = bulletToGLM(bV);
    
    QCOMPARE(gV.x, bV.getX());
    QCOMPARE(gV.y, bV.getY());
    QCOMPARE(gV.z, bV.getZ());

    float angle = 0.317f * PI;
    btVector3 axis(1.23f, 2.34f, 3.45f);
    axis.normalize();
    btQuaternion bQ(axis, angle);

    glm::quat gQ = bulletToGLM(bQ);
    QCOMPARE(gQ.x, bQ.getX());
    QCOMPARE(gQ.y, bQ.getY());
    QCOMPARE(gQ.z, bQ.getZ());
    QCOMPARE(gQ.w, bQ.getW());

    // mat4
    btMatrix3x3 basis(bQ);
    btVector3 origin(100.0f, 200.0f, 300.0f);
    btTransform bM(basis, origin);

    glm::mat4 gM = bulletToGLM(bM);

    glm::vec3 translation = extractTranslation(gM);
    QCOMPARE(translation.x, bM.getOrigin().getX());
    QCOMPARE(translation.y, bM.getOrigin().getY());
    QCOMPARE(translation.z, bM.getOrigin().getZ());

    glm::quat rotation = glmExtractRotation(gM);
    QCOMPARE(rotation.x, bM.getRotation().getX());
    QCOMPARE(rotation.y, bM.getRotation().getY());
    QCOMPARE(rotation.z, bM.getRotation().getZ());
    QCOMPARE(rotation.w, bM.getRotation().getW());

    // As a sanity check, transform vectors by their corresponding matrices and compare the result.
    btVector3 bX = bM * btVector3(1.0f, 0.0f, 0.0f);
    btVector3 bY = bM * btVector3(0.0f, 1.0f, 0.0f);
    btVector3 bZ = bM * btVector3(0.0f, 0.0f, 1.0f);

    glm::vec3 gX = transformPoint(gM, glm::vec3(1.0f, 0.0f, 0.0f));
    glm::vec3 gY = transformPoint(gM, glm::vec3(0.0f, 1.0f, 0.0f));
    glm::vec3 gZ = transformPoint(gM, glm::vec3(0.0f, 0.0f, 1.0f));

    QCOMPARE(gX.x, bX.getX());
    QCOMPARE(gX.y, bX.getY());
    QCOMPARE(gX.z, bX.getZ());
    QCOMPARE(gY.x, bY.getX());
    QCOMPARE(gY.y, bY.getY());
    QCOMPARE(gY.z, bY.getZ());
    QCOMPARE(gZ.x, bZ.getX());
    QCOMPARE(gZ.y, bZ.getY());
    QCOMPARE(gZ.z, bZ.getZ());
}

void BulletUtilTests::fromGLMToBullet() {
    glm::vec3 gV(1.23f, 4.56f, 7.89f);
    btVector3 bV = glmToBullet(gV);

    QCOMPARE(gV.x, bV.getX());
    QCOMPARE(gV.y, bV.getY());
    QCOMPARE(gV.z, bV.getZ());

    float angle = 0.317f * PI;
    btVector3 axis(1.23f, 2.34f, 3.45f);
    axis.normalize();
    btQuaternion bQ(axis, angle);

    glm::quat gQ = bulletToGLM(bQ);
    QCOMPARE(gQ.x, bQ.getX());
    QCOMPARE(gQ.y, bQ.getY());
    QCOMPARE(gQ.z, bQ.getZ());
    QCOMPARE(gQ.w, bQ.getW());

    // mat3
    glm::mat3 gM3 = glm::mat3_cast(gQ);
    btMatrix3x3 bM3 = glmToBullet(gM3);
    bM3.getRotation(bQ);
    QCOMPARE(gQ.x, bQ.getX());
    QCOMPARE(gQ.y, bQ.getY());
    QCOMPARE(gQ.z, bQ.getZ());
    QCOMPARE(gQ.w, bQ.getW());

    // mat4
    glm::mat4 gM4 = createMatFromQuatAndPos(gQ, gV);
    btTransform bM4 = glmToBullet(gM4);
    bQ = bM4.getRotation();
    bV = bM4.getOrigin();
    QCOMPARE(gQ.x, bQ.getX());
    QCOMPARE(gQ.y, bQ.getY());
    QCOMPARE(gQ.z, bQ.getZ());
    QCOMPARE(gQ.w, bQ.getW());
    QCOMPARE(gV.x, bV.getX());
    QCOMPARE(gV.y, bV.getY());
    QCOMPARE(gV.z, bV.getZ());
}

void BulletUtilTests::rotateVectorTest() {

    float angle = 0.317f * PI;
    btVector3 axis(1.23f, 2.34f, 3.45f);
    axis.normalize();
    btQuaternion q(axis, angle);

    btVector3 xAxis(1.0f, 0.0f, 0.0f);

    btVector3 result0 = rotateVector(q, xAxis);

    btTransform m(q);
    btVector3 result1 = m * xAxis;

    QCOMPARE(result0.getX(), result0.getX());
    QCOMPARE(result0.getY(), result1.getY());
    QCOMPARE(result0.getZ(), result1.getZ());
}

void BulletUtilTests::clampLengthTest() {
    btVector3 vec(1.0f, 3.0f, 2.0f);
    btVector3 clampedVec1 = clampLength(vec, 1.0f);
    btVector3 clampedVec2 = clampLength(vec, 2.0f);
    btVector3 normalizedVec = vec.normalized();

    QCOMPARE(clampedVec1.getX(), normalizedVec.getX());
    QCOMPARE(clampedVec1.getY(), normalizedVec.getY());
    QCOMPARE(clampedVec1.getZ(), normalizedVec.getZ());

    QCOMPARE(clampedVec2.getX(), normalizedVec.getX() * 2.0f);
    QCOMPARE(clampedVec2.getY(), normalizedVec.getY() * 2.0f);
    QCOMPARE(clampedVec2.getZ(), normalizedVec.getZ() * 2.0f);
}
