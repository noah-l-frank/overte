// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import "ShareJournal.h"
#include <sys/stat.h>

@interface OVTShareRead : NSObject
@property(nonatomic,strong) OVTShareJournal* journal;
@end
@implementation OVTShareRead
- (void)dealloc {[self.journal event:@"weak-expired"];}
@end

@interface OVTShareReceiver : UIViewController
@property(nonatomic,strong) UITextField* runField;
@property(nonatomic,strong) UITextField* nameField;
@property(nonatomic,strong) UITextField* queryField;
@property(nonatomic,strong) UILabel* status;
@property(nonatomic,strong) OVTShareJournal* journal;
@end
@implementation OVTShareReceiver
- (UITextField*)field:(NSString*)name placeholder:(NSString*)placeholder stack:(UIStackView*)stack {
    UITextField* field=[UITextField new];field.borderStyle=UITextBorderStyleRoundedRect;
    field.autocorrectionType=UITextAutocorrectionTypeNo;field.autocapitalizationType=UITextAutocapitalizationTypeNone;
    field.accessibilityIdentifier=name;field.placeholder=placeholder;[stack addArrangedSubview:field];return field;
}
- (void)button:(NSString*)title name:(NSString*)name action:(SEL)action stack:(UIStackView*)stack {
    UIButton* button=[UIButton buttonWithType:UIButtonTypeSystem];[button setTitle:title forState:UIControlStateNormal];
    button.accessibilityIdentifier=name;[button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];[stack addArrangedSubview:button];
}
- (void)viewDidLoad {
    [super viewDidLoad];self.view.backgroundColor=UIColor.systemBackgroundColor;
    UIStackView* stack=[UIStackView new];stack.axis=UILayoutConstraintAxisVertical;stack.spacing=12;stack.translatesAutoresizingMaskIntoConstraints=NO;
    [self.view addSubview:stack];[NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.trailingAnchor constant:-20],
        [stack.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20]]];
    self.runField=[self field:@"snapshot.share.run" placeholder:@"Run identifier" stack:stack];
    self.nameField=[self field:@"snapshot.share.basename" placeholder:@"Observed original capture filename" stack:stack];
    self.queryField=[self field:@"snapshot.share.query" placeholder:@"Fresh inspection nonce" stack:stack];
    [self button:@"Receive original file" name:@"snapshot.share.receive" action:@selector(receiveOriginal) stack:stack];
    [self button:@"Inspect original owner" name:@"snapshot.share.inspect" action:@selector(inspectOriginal) stack:stack];
    [self button:@"Finish receiving" name:@"snapshot.share.finish" action:@selector(finishOriginal) stack:stack];
    [self button:@"Cancel" name:@"snapshot.share.cancel" action:@selector(cancelOriginal) stack:stack];
    self.status=[UILabel new];self.status.numberOfLines=0;self.status.accessibilityIdentifier=@"snapshot.share.status";
    self.status.text=@"No original received";[stack addArrangedSubview:self.status];
}
- (void)receiveOriginal {
    // Retain unknown/failed attempts; repeated buttons or process reconstruction
    // never request another provider representation for an existing run.
    if (self.journal) {self.status.text=@"Responsibility already retained";return;}
    NSString* run=self.runField.text,*name=self.nameField.text;
    if (!OVTShareMatch(run,@"\\A[0-9a-f]{32}\\z") || !OVTShareMatch(name,@"\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)\\z")
            || ![name hasPrefix:[NSString stringWithFormat:@"parity-%@-",[run substringToIndex:16]]]) {self.status.text=@"Invalid owned capture identity";return;}
    NSArray* items=self.extensionContext.inputItems;
    if (items.count!=1 || ![items.firstObject isKindOfClass:NSExtensionItem.class]) {self.status.text=@"Ambiguous extension input";return;}
    NSArray<NSItemProvider*>* attachments=((NSExtensionItem*)items.firstObject).attachments;
    if (attachments.count!=1) {self.status.text=@"Exactly one original attachment required";return;}
    NSItemProvider* provider=attachments.firstObject;NSArray<NSString*>* registered=provider.registeredTypeIdentifiers;
    if (registered.count<1 || registered.count>32) {self.status.text=@"Invalid provider types";return;}
    NSMutableArray<NSString*>* types=[NSMutableArray new];
    for (NSString* identifier in registered) {
        if (![identifier isKindOfClass:NSString.class] || identifier.length<1 || identifier.length>256) {self.status.text=@"Invalid provider type";return;}
        UTType* type=[UTType typeWithIdentifier:identifier];
        // Select an actually advertised concrete image type. A generic image
        // conversion or preview is not an original file representation.
        if ([type conformsToType:UTTypeImage] && [type isEqual:[UTType typeWithFilenameExtension:name.pathExtension]]) {[types addObject:identifier];}
    }
    if (types.count!=1) {self.status.text=@"Ambiguous original representation";return;}
    NSURL* group=OVTShareGroup();if (!group) {self.status.text=@"App Group unavailable";return;}
    NSURL* root=[group URLByAppendingPathComponent:[@"snapshot-share-" stringByAppendingString:run] isDirectory:YES];
    if (mkdir(root.fileSystemRepresentation,0700)!=0) {self.status.text=@"Existing or unavailable original; no reissue";return;}
    OVTShareJournal* journal=[OVTShareJournal new];journal.root=root;self.journal=journal;
    journal.record=[@{@"iosSnapshotShareOriginalVersion":@1,@"runId":run,@"basename":name,@"instance":OVTShareID(),
        @"processId":@(NSProcessInfo.processInfo.processIdentifier),@"receiverBundleId":NSBundle.mainBundle.bundleIdentifier,
        @"clockDomain":@"native-share-extension",@"createdClock":OVTShareClock(),@"phase":@"issued",@"artifact":@"original.bytes",
        @"attachmentCount":@(attachments.count),@"registeredTypes":registered,@"selectedType":types.firstObject,
        @"receivedFilename":NSNull.null,@"byteCount":@0,@"sha256":@"",@"events":[NSMutableArray new],@"queries":[NSMutableArray new]} mutableCopy];
    if (![journal event:@"read-issued"]) {self.status.text=@"Intent persistence failed";return;}
    OVTShareRead* operation=[OVTShareRead new];operation.journal=journal;journal.operation=operation;
    // Apple's temporary representation exists only during the actual callback.
    // Copy unchanged bytes here, before returning; never UIImage/re-encode.
    [provider loadFileRepresentationForTypeIdentifier:types.firstObject completionHandler:^(NSURL* url,NSError* error) {
        OVTShareJournal* actual=operation.journal;[actual.lock lock];
        BOOL entered=[actual event:@"callback-enter"];NSString* hash=nil;NSUInteger count=0;
        BOOL valid=entered && !error && url.isFileURL && [url.lastPathComponent isEqual:actual.record[@"basename"]];
        if (valid) {
            actual.record[@"receivedFilename"]=url.lastPathComponent;
            valid=OVTShareCopyFile(url,[actual.root URLByAppendingPathComponent:@"original.bytes"],&hash,&count);
        }
        actual.record[@"phase"]=valid?@"complete":@"failed";
        if (valid) {actual.record[@"byteCount"]=@(count);actual.record[@"sha256"]=hash;}
        [actual event:valid?@"read-completed":@"read-failed"];[actual event:@"callback-left"];[actual.lock unlock];
    }];
    self.status.text=@"Original requested once; inspect its actual owner";
}
- (void)inspectOriginal {
    OVTShareJournal* journal=self.journal;NSString* request=self.queryField.text;
    if (!journal || !OVTShareMatch(request,@"\\Aios-[0-9a-f]{32}\\z")) {return;}
    [journal.lock lock];NSMutableArray* queries=journal.record[@"queries"];
    for (NSDictionary* old in queries) {if ([old[@"requestId"] isEqual:request]) {[journal.lock unlock];return;}}
    if (!journal.valid || queries.count>=128) {journal.valid=NO;[journal.lock unlock];return;}
    [queries addObject:@{@"requestId":request,@"clock":OVTShareClock(),@"operationAlive":@(journal.operation!=nil)}];
    BOOL saved=[journal persist];[journal.lock unlock];self.status.text=saved?@"Original inspection persisted":@"Inspection failed";
}
- (void)finishOriginal {
    OVTShareJournal* journal=self.journal;if (!journal) {return;}[journal.lock lock];
    NSMutableArray* events=journal.record[@"events"];BOOL inspected=NO;
    for (NSDictionary* query in journal.record[@"queries"]) {if (![query[@"operationAlive"] boolValue]) {inspected=YES;}}
    for (NSDictionary* event in events) {if ([event[@"kind"] isEqual:@"finish-issued"]) {[journal.lock unlock];return;}}
    if (!journal.valid || journal.operation || !inspected || ![journal.record[@"phase"] isEqual:@"complete"]
            || ![journal event:@"finish-issued"]) {[journal.lock unlock];return;}
    [journal.lock unlock];
    // This starts extension termination. It is expressly not a process-absence
    // or native callback-drain receipt; the enclosing owner must prove those.
    [self.extensionContext completeRequestReturningItems:@[] completionHandler:nil];
}
- (void)cancelOriginal {
    [self.extensionContext cancelRequestWithError:[NSError errorWithDomain:NSCocoaErrorDomain code:NSUserCancelledError userInfo:nil]];
}
@end
