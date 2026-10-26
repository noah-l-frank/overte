// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <Foundation/Foundation.h>

typedef NS_ENUM(NSUInteger, OVTShareSourceOutput) {
    OVTShareSourceChunk=0, OVTShareSourceRetireIntent=1,
    OVTShareSourceRetireResult=2, OVTShareSourceRetireObservation=3
};
// Only this Archive's four literal global producers. No arbitrary path API.
@interface OVTShareSourceOutputs : NSObject
+ (instancetype)shared;
- (BOOL)publish:(OVTShareSourceOutput)kind bytes:(NSData*)bytes;
- (void)freezeWithAdmissionSeal:(NSData*)original;
- (BOOL)producersFrozen;
- (BOOL)inventoryReady;
- (NSData*)inventory:(NSString*)nonce;
- (NSData*)inventoryOriginal;
@end
