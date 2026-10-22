// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <Foundation/Foundation.h>
#if !defined(OVERTE_E2E_FEATURE_TESTS)
#error The Snapshot Share receiver is a separate explicitly selected E2E target.
#endif
FOUNDATION_EXPORT NSDictionary* OVTShareClock(void);
FOUNDATION_EXPORT NSString* OVTShareID(void);
FOUNDATION_EXPORT BOOL OVTShareMatch(NSString* value,NSString* expression);
FOUNDATION_EXPORT NSURL* OVTShareGroup(void);
FOUNDATION_EXPORT BOOL OVTShareCopyFile(NSURL* source,NSURL* destination,NSString** hash,NSUInteger* count);
FOUNDATION_EXPORT BOOL OVTShareWrite(NSURL* root,NSString* basename,NSData* bytes);
FOUNDATION_EXPORT NSData* OVTShareReadMetadata(NSURL* source);
@interface OVTShareJournal : NSObject
@property(nonatomic,strong) NSRecursiveLock* lock;
@property(nonatomic,strong) NSURL* root;
@property(nonatomic,strong) NSMutableDictionary* record;
@property(nonatomic,weak) NSObject* operation;
@property BOOL valid;
- (BOOL)persist;
- (BOOL)event:(NSString*)kind;
@end
