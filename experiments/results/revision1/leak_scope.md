# Revision 1 — scope of the B_noVolatile leak and B_noVolatileConsistent controls

Zero model calls. Observations rebuilt with `DUMP_OBSERVATIONS=1` (`Observation.BuildObservationAsync`, same DOM walk and encoders as the corpus run); predicate verdicts from `Oracle.LocatorUsesVolatileSignal` via `AttributeBundles.PredicateFlagsClassToken` / `PredicateFlagsId` (`[class~="tok"]` / `[id="id"]` forms).

**Gate: PASS** — conflicts_empty=yes, condition5_identical_960=yes, condition5_matches_stored_960=yes, token_fidelity=yes, dump_guard_clean=yes, python_port_agrees_with_predicate=yes, differing_pages_equal_leak_pages=yes

## 1. Fidelity of the rebuilt observations

Dumped token count vs stored `observation_tokens` for B_full×F1 and B_noVolatile×F0–F3: 120 cells, 0 mismatches.

## 2. Token census (raw DOM walk, per page distinct tokens, summed over 24 pages)

| kind | distinct (page,token) | predicate flags | listed | BEM base | regex |
|---|---|---|---|---|---|
| class | 1226 | 285 | 110 | 2 | 197 |
| id | 236 | 29 | 29 | 0 | 0 |

Python port of the predicate vs C# verdict: 0 disagreements.

### 2a. Tokens flagged by the predicate, neither listed nor a BEM base (the leak)

Class tokens: 173; ids: 0; pages: page_17, page_18, page_21, page_22, page_23, page_24.

- **class**: page_17: `ActionMenu_editBtn__l8m9n0`, `ActionMenu_moreBtn__r4s5t6`, `AdminLayout_avatar__m6n7o8`, `AdminLayout_brand__d4e5f6`, `AdminLayout_footer__z5a6b7`, `AdminLayout_headerRight__h0i1j2`, `AdminLayout_header__a1b2c3`, `AdminLayout_pageTitle__m6n7o8`, `AdminLayout_subTitle__p9q0r1`, `AdminLayout_toolbar__m3n4o5`, `AdminLayout_userLabel__k3l4m5`, `ConsolePanel_badge__f1g2h3`, `ConsolePanel_detailHead__b1c2d3`, `ConsolePanel_detailWrap__z8a9b0`, `ConsolePanel_editBtn__l7m8n9`, `ConsolePanel_toggleInput__w6x7y8`, `ConsolePanel_toggleLabel__p0q1r2`, `ConsolePanel_toggleThumb__u3v4w5`, `ConsolePanel_toggleTrack__r0s1t2`, `ConsolePanel_toggleWrap__i4j5k6`, `ConsolePanel_userEmail__o7p8q9`, `ConsolePanel_userInfo__j1k2l3`, `ConsolePanel_userName__l4m5n6`, `EditPanel_cancelBtn__u3v4w5`, `EditPanel_field__g8h9i0`, `EditPanel_footer__s0t1u2`, `EditPanel_input__m4n5o6`, `EditPanel_label__j1k2l3`, `EditPanel_saveBtn__x6y7z8`, `EditPanel_select__p7q8r9`, `EditPanel_title__d5e6f7`, `PaginationBar_controls__t5u6v7`, `PaginationBar_label__u6v7w8`, `PaginationBar_prevBtn__r3s4t5`, `StatusBadge_label__s0t1u2`, `Toolbar_exportBtn__h7i8j9`, `Toolbar_newUserBtn__e4f5g6`, `Toolbar_roleFilter__b1c2d3`, `Toolbar_searchIcon__v5w6x7`, `Toolbar_searchInput__y8z9a0`, `Toolbar_searchWrap__s2t3u4`, `Toolbar_statsChip__i0j1k2`, `UserAvatar_initials__y9z0a1`, `UserCell_email__h8i9j0`, `UserCell_stack__b2c3d4`, `UserCell_username__e5f6g7`, `UsersTable_wrapper__p6q7r8`; page_18: `AppHeader_avatar__z3a4b5`, `AppHeader_navLink__w0x1y2`, `BoardToolbar_btnGroup__r7s8t9`, `BoardToolbar_filterInput__l1m2n3`, `BoardToolbar_iconBtn__u0v1w2`, `BoardToolbar_newBtn__o4p5q6`, `BoardToolbar_title__f5g6h7`, `EditPanel_actions__e2f3g4`, `EditPanel_cancelBtn__h5i6j7`, `EditPanel_field__s0t1u2`, `EditPanel_saveBtn__k8l9m0`, `EditPanel_title__p7q8r9`, `KanbanCard_assignee__v2w3x4`, `KanbanCard_footer__s9t0u1`, `KanbanCard_header__d4e5f6`, `KanbanCard_title__m3n4o5`, `KanbanCol_count__u0v1w2`, `KanbanCol_header__o4p5q6`, `KanbanCol_title__r7s8t9`, `KanbanPanel_addBtn__w9x0y1`, `KanbanPanel_editHead__g0h1i2`, `KanbanPanel_editSection__c5d6e7`, `KanbanPanel_sortLbl__a4b5c6`, `KanbanPanel_sortSel__d7e8f9`, `KanbanPanel_title__q3r4s5`; page_21: `ChannelInfo_avatar__k4l5m6`, `ChannelInfo_details__n7o8p9`, `CommentCard_actions__g2h3i4`, `CommentCard_author__a6b7c8`, `CommentCard_avatar__u0v1w2`, `CommentCard_likeBtn__j5k6l7`, `CommentCard_replyBtn__m8n9o0`, `Comments_heading__i8j9k0`, `Comments_section__f5g6h7`, `Comments_sortBtn__o4p5q6`, `Comments_sortIcon__j1k2l3`, `Comments_sortRow__l1m2n3`, `ControlBar_container__h8i9j0`, `Description_moreBtn__c2d3e4`, `Description_stats__a1b2c3`, `Footer_inner__t7u8v9`, `Footer_links__w0x1y2`, `Header_actions__r9s0t1`, `Header_inner__c4d5e6`, `Header_search__i0j1k2`, `Header_signInBtn__x5y6z7`, `Header_uploadBtn__u2v3w4`, `PageLayout_footer__q4r5s6`, `PageLayout_header__z1a2b3`, `PageLayout_sidebar__p1q2r3`, `PageLayout_videoCol__d1e2f3`, `PlayerHost_shell__g4h5i6`, `SearchBar_input__l3m4n5`, `SidePanel_channel__h9i0j1`, `SidePanel_thumb__y0z1a2`, `SidePanel_title__e6f7g8`, `Sidebar_heading__v7w8x9`, `Sidebar_section__s4t5u6`, `VideoMeta_actions__v9w0x1`, `VideoMeta_channelRow__h1i2j3`, `VideoMeta_container__c1d2e3`, `VideoMeta_dislikeBtn__y2z3a4`, `VideoMeta_moreBtn__h1i2j3`, `VideoMeta_saveBtn__e8f9g0`, `VideoMeta_shareBtn__b5c6d7`, `VideoMeta_stats__m0n1o2`, `VideoMeta_title__j7k8l9`, `VideoMeta_views__p3q4r5`, `VideoPlayer_paused__c8d9e0`, `VideoPlayer_viewport__b1c2d3`, `VideoPlayer_wrapper__f3g4h5`; page_22: `EditForm_actions__k8l9m0`, `EditForm_cancelBtn__n1o2p3`, `EditForm_field__v3w4x5`, `EditForm_saveBtn__q4r5s6`, `EditForm_title__s0t1u2`, `TfAction_count__d4e5f6`, `TfAction_refreshBtn__a1b2c3`, `TfHeader_navLink__w0x1y2`, `TfSearch_dateInp__u0v1w2`, `TfSearch_dateWrap__r7s8t9`, `TfSearch_label__f5g6h7`, `TrackPanel_carrierSel__c6d7e8`, `TrackPanel_ctrlLbl__z3a4b5`, `TrackPanel_detailCard__i2j3k4`, `TrackPanel_detailHead__l5m6n7`, `TrackPanel_detailTitle__o8p9q0`, `TrackPanel_editSection__a0b1c2`, `TrackPanel_exportBtn__f9g0h1`, `TrackPanel_infoKey__u4v5w6`, `TrackPanel_infoRow__r1s2t3`, `TrackPanel_infoVal__x7y8z9`; page_23: `Checkout_layout__h6j7k8`, `Checkout_right__c2v3b4`, `Header_tagline__r4t5y6`, `OrderItem_price__m3n4o5`, `OrderSummary_header__n5m6l7`, `OrderSummary_total__k8j9h0`, `PayShell_secRow__q1r2s3`, `PayShell_secText__t4u5v6`, `PayShell_title__h2i3j4`, `PayWidget_checkRow__h9i0j1`, `PayWidget_field__e6f7g8`, `PayWidget_submitBtn__k2l3m4`, `PromoRow_input__k0l1m2`, `ShippingForm_field__o1p2a3`, `ShippingForm_title__y8u9i0`; page_24: `AccountSection_actions__e1f2g3`, `AccountSection_btnOutline__k7l8m9`, `AccountSection_field__b8c9d0`, `NotifSection_header__n0o1p2`, `NotifSection_title__q3r4s5`, `PrefPanel_checkRow__v9w0x1`, `PrefPanel_saveBtn__y2z3a4`, `PrefPanel_title__q3r4s5`, `Section_title__y5z6a7`, `SettingRow_label__f4g5h6`, `SettingRow_slider__r6s7t8`, `SettingRow_status__u9v0w1`, `SettingRow_toggle__o3p4q5`, `SettingsPanel_check__f8g9h0`, `SettingsPanel_title__e4f5g6`, `SettingsPanel_toggleDesc__n3o4p5`, `SettingsPanel_toggleLabel__k0l1m2`, `SettingsPanel_toggleRow__h7i8j9`, `SideNav_title__j0k1l2`
- **id**: none

### 2b. Where the leaked tokens appear in the observations (element count carrying the token; NV = B_noVolatile, NVC = B_noVolatileConsistent)

| page | kind | token | NV F0 | NV F1 | NV F2 | NV F3 | NVC F0 | NVC F1 | NVC F2 | NVC F3 | NV locators using it (by enc) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| page_17 | class | `ActionMenu_editBtn__l8m9n0` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `ActionMenu_moreBtn__r4s5t6` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_avatar__m6n7o8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_brand__d4e5f6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_footer__z5a6b7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_headerRight__h0i1j2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_header__a1b2c3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_pageTitle__m6n7o8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_subTitle__p9q0r1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_toolbar__m3n4o5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `AdminLayout_userLabel__k3l4m5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_badge__f1g2h3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_detailHead__b1c2d3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_detailWrap__z8a9b0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_editBtn__l7m8n9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_toggleInput__w6x7y8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `ConsolePanel_toggleLabel__p0q1r2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_toggleThumb__u3v4w5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_toggleTrack__r0s1t2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_toggleWrap__i4j5k6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_userEmail__o7p8q9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_userInfo__j1k2l3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `ConsolePanel_userName__l4m5n6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `EditPanel_cancelBtn__u3v4w5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `EditPanel_field__g8h9i0` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `EditPanel_footer__s0t1u2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `EditPanel_input__m4n5o6` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 6 {'F0': 2, 'F1': 2, 'F2': 1, 'F3': 1} |
| page_17 | class | `EditPanel_label__j1k2l3` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `EditPanel_saveBtn__x6y7z8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `EditPanel_select__p7q8r9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 3 {'F0': 1, 'F1': 1, 'F3': 1} |
| page_17 | class | `EditPanel_title__d5e6f7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `PaginationBar_controls__t5u6v7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 2 {'F2': 1, 'F3': 1} |
| page_17 | class | `PaginationBar_label__u6v7w8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `PaginationBar_prevBtn__r3s4t5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 2 {'F2': 1, 'F3': 1} |
| page_17 | class | `StatusBadge_label__s0t1u2` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `Toolbar_exportBtn__h7i8j9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `Toolbar_newUserBtn__e4f5g6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `Toolbar_roleFilter__b1c2d3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `Toolbar_searchIcon__v5w6x7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `Toolbar_searchInput__y8z9a0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `Toolbar_searchWrap__s2t3u4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `Toolbar_statsChip__i0j1k2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `UserAvatar_initials__y9z0a1` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `UserCell_email__h8i9j0` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `UserCell_stack__b2c3d4` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_17 | class | `UserCell_username__e5f6g7` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_17 | class | `UsersTable_wrapper__p6q7r8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `AppHeader_avatar__z3a4b5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `AppHeader_navLink__w0x1y2` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `BoardToolbar_btnGroup__r7s8t9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `BoardToolbar_filterInput__l1m2n3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `BoardToolbar_iconBtn__u0v1w2` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `BoardToolbar_newBtn__o4p5q6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `BoardToolbar_title__f5g6h7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `EditPanel_actions__e2f3g4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `EditPanel_cancelBtn__h5i6j7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `EditPanel_field__s0t1u2` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `EditPanel_saveBtn__k8l9m0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `EditPanel_title__p7q8r9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanCard_assignee__v2w3x4` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanCard_footer__s9t0u1` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanCard_header__d4e5f6` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 3 {'F0': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `KanbanCard_title__m3n4o5` | 200 | 200 | 200 | 200 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanCol_count__u0v1w2` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 1 {'F1': 1} |
| page_18 | class | `KanbanCol_header__o4p5q6` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanCol_title__r7s8t9` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanPanel_addBtn__w9x0y1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `KanbanPanel_editHead__g0h1i2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanPanel_editSection__c5d6e7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanPanel_sortLbl__a4b5c6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_18 | class | `KanbanPanel_sortSel__d7e8f9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_18 | class | `KanbanPanel_title__q3r4s5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F0': 1} |
| page_21 | class | `ChannelInfo_avatar__k4l5m6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `ChannelInfo_details__n7o8p9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `CommentCard_actions__g2h3i4` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `CommentCard_author__a6b7c8` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `CommentCard_avatar__u0v1w2` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `CommentCard_likeBtn__j5k6l7` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `CommentCard_replyBtn__m8n9o0` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Comments_heading__i8j9k0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Comments_section__f5g6h7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Comments_sortBtn__o4p5q6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Comments_sortIcon__j1k2l3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Comments_sortRow__l1m2n3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `ControlBar_container__h8i9j0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 2 {'F0': 1, 'F3': 1} |
| page_21 | class | `Description_moreBtn__c2d3e4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Description_stats__a1b2c3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Footer_inner__t7u8v9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Footer_links__w0x1y2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Header_actions__r9s0t1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Header_inner__c4d5e6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Header_search__i0j1k2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Header_signInBtn__x5y6z7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Header_uploadBtn__u2v3w4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `PageLayout_footer__q4r5s6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `PageLayout_header__z1a2b3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `PageLayout_sidebar__p1q2r3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F3': 1} |
| page_21 | class | `PageLayout_videoCol__d1e2f3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `PlayerHost_shell__g4h5i6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `SearchBar_input__l3m4n5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `SidePanel_channel__h9i0j1` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `SidePanel_thumb__y0z1a2` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `SidePanel_title__e6f7g8` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Sidebar_heading__v7w8x9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `Sidebar_section__s4t5u6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_actions__v9w0x1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_channelRow__h1i2j3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_container__c1d2e3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_dislikeBtn__y2z3a4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_moreBtn__h1i2j3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_saveBtn__e8f9g0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_shareBtn__b5c6d7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_stats__m0n1o2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_title__j7k8l9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoMeta_views__p3q4r5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoPlayer_paused__c8d9e0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoPlayer_viewport__b1c2d3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_21 | class | `VideoPlayer_wrapper__f3g4h5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 2 {'F2': 1, 'F3': 1} |
| page_22 | class | `EditForm_actions__k8l9m0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `EditForm_cancelBtn__n1o2p3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `EditForm_field__v3w4x5` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `EditForm_saveBtn__q4r5s6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_22 | class | `EditForm_title__s0t1u2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TfAction_count__d4e5f6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TfAction_refreshBtn__a1b2c3` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_22 | class | `TfHeader_navLink__w0x1y2` | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TfSearch_dateInp__u0v1w2` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TfSearch_dateWrap__r7s8t9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TfSearch_label__f5g6h7` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TrackPanel_carrierSel__c6d7e8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_22 | class | `TrackPanel_ctrlLbl__z3a4b5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TrackPanel_detailCard__i2j3k4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F0': 1} |
| page_22 | class | `TrackPanel_detailHead__l5m6n7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 2 {'F2': 1, 'F3': 1} |
| page_22 | class | `TrackPanel_detailTitle__o8p9q0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TrackPanel_editSection__a0b1c2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F1': 1} |
| page_22 | class | `TrackPanel_exportBtn__f9g0h1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_22 | class | `TrackPanel_infoKey__u4v5w6` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TrackPanel_infoRow__r1s2t3` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_22 | class | `TrackPanel_infoVal__x7y8z9` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `Checkout_layout__h6j7k8` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `Checkout_right__c2v3b4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `Header_tagline__r4t5y6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `OrderItem_price__m3n4o5` | 90 | 90 | 90 | 90 | 0 | 0 | 0 | 0 | 1 {'F0': 1} |
| page_23 | class | `OrderSummary_header__n5m6l7` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `OrderSummary_total__k8j9h0` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `PayShell_secRow__q1r2s3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 3 {'F1': 1, 'F2': 1, 'F3': 1} |
| page_23 | class | `PayShell_secText__t4u5v6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F0': 1} |
| page_23 | class | `PayShell_title__h2i3j4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `PayWidget_checkRow__h9i0j1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `PayWidget_field__e6f7g8` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `PayWidget_submitBtn__k2l3m4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_23 | class | `PromoRow_input__k0l1m2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `ShippingForm_field__o1p2a3` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0  |
| page_23 | class | `ShippingForm_title__y8u9i0` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `AccountSection_actions__e1f2g3` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `AccountSection_btnOutline__k7l8m9` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 3 {'F0': 1, 'F2': 1, 'F3': 1} |
| page_24 | class | `AccountSection_field__b8c9d0` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `NotifSection_header__n0o1p2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_24 | class | `NotifSection_title__q3r4s5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 3 {'F0': 1, 'F1': 1, 'F2': 1} |
| page_24 | class | `PrefPanel_checkRow__v9w0x1` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `PrefPanel_saveBtn__y2z3a4` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 4 {'F0': 1, 'F1': 1, 'F2': 1, 'F3': 1} |
| page_24 | class | `PrefPanel_title__q3r4s5` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F3': 1} |
| page_24 | class | `Section_title__y5z6a7` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingRow_label__f4g5h6` | 70 | 70 | 70 | 70 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingRow_slider__r6s7t8` | 70 | 70 | 70 | 70 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingRow_status__u9v0w1` | 70 | 70 | 70 | 70 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingRow_toggle__o3p4q5` | 70 | 70 | 70 | 70 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingsPanel_check__f8g9h0` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 8 {'F0': 2, 'F1': 2, 'F2': 2, 'F3': 2} |
| page_24 | class | `SettingsPanel_title__e4f5g6` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 {'F3': 1} |
| page_24 | class | `SettingsPanel_toggleDesc__n3o4p5` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingsPanel_toggleLabel__k0l1m2` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SettingsPanel_toggleRow__h7i8j9` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0  |
| page_24 | class | `SideNav_title__j0k1l2` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0  |

B_noVolatile records with `predicate_non_volatile = false`: 119; records whose locator literally contains a leaked token: 114 (non_volatile=false: 114); by failure mode {'model_grabbed_brittle_signal': 84, 'observation_lacked_stable_signal': 30}; by page {'page_17': 35, 'page_18': 25, 'page_21': 5, 'page_22': 20, 'page_23': 9, 'page_24': 20}. The earlier investigation (`volatile_in_noVolatile.md`) covered only the grabbed failures (84); the lacked ones lie outside it.
Leaked tokens used in at least one B_noVolatile locator: 40 of 173.

Leaked tokens absent from every B_noVolatile observation: 0 of 173.
Leaked tokens present in any B_noVolatileConsistent observation: 0.

### 2c. Prefix / substring forms

Tokens kept by both bundles (not flagged in `~=`/`=` form) that are a prefix of a listed volatile token, i.e. would be flagged if the model wrote `[class^=…]`/`[class*=…]`/`[id^=…]`/`[id*=…]`: 4. page_05 class `pagination`; page_07 class `hero`; page_08 class `pagination`; page_08 class `sidebar`
Fragments of a removed token cannot be written from the observation, since the token is absent.

### 2d. Class/id tokens with CSS-special characters

Tokens in the DOM census that are not plain CSS identifiers: 0.
The bundle consults the predicate only through `[class~="…"]` / `[id="…"]`; synthetic special-character tokens are covered by unit tests in `experiments/tests`.

## 3. The 22 class names of §3.3

Source: `BemDedupParityTests` (`shared/oracle.tests/LocatorVolatilityTests.cs`). It compares `Oracle.IsBemBaseOfVolatile` with the strip path of `ApplyBundleNoVolatile` against 4 hard-coded volatile classes (`gallery__nav-btn--next--b3c4d5`, `pkg-select--a9b8c7`, `price-tag--vue-d4e5f6`, `data-v-7ba5bd90`).

- Names: `gallery__nav-btn--next`, `gallery__nav-btn`, `pkg-select`, `price-tag`, `btn`, `btn-primary`, `btn-search`, `form-select`, `nav-search`, `add-to-cart-btn`, `qty-input`, `write-review-btn`, `breadcrumb`, `notice-bar`, `notice-bar__inner`, `header-search`, `header-search__btn`, `header-utils__btn`, `mm-panel`, `nav-bar`, `list-item`, `tab-content`.
- Names matching `VolatileClassRe`: none.
- Intersection with the leaked tokens: none.
- Names present in the testbed DOM: 14 of 22.
- The test exercises only the BEM rule (each name is asserted not to be a literal volatile class), on a hand-written element, with no regex-matching name and no page DOM. A token flagged by `VolatileClassRe` but missing from `volatile_classes` is outside what the test can observe.

## 4. Stable id/class signals vs the predicate (CONFLICT list)

Targets with an `id`/`class` entry in `signal_attrs`: 50. Distinct (target, attr, value): 50; listed: 0; predicate-flagged: 0.

**CONFLICTS: 0**

## 5. Condition 5 (stable_signal_present_in_bundle)

B_noVolatile vs B_noVolatileConsistent over 960 (target × F0–F3): 0 differences. Rebuilt B_noVolatile vs stored records: 0 differences.
True counts: B_noVolatile 768, B_noVolatileConsistent 768, stored 768 (of 960). `lacked` is therefore unchanged.

## 6. Byte comparison B_noVolatile vs B_noVolatileConsistent

Identical: 72 of 96; differing: 24 (pages page_17, page_18, page_21, page_22, page_23, page_24).

| page | enc | tokens NV | tokens NVC | Δ |
|---|---|---|---|---|
| page_17 | F0 | 92432 | 73981 | -18451 |
| page_17 | F1 | 107788 | 88327 | -19461 |
| page_17 | F2 | 107531 | 88072 | -19459 |
| page_17 | F3 | 81880 | 63876 | -18004 |
| page_18 | F0 | 58542 | 47377 | -11165 |
| page_18 | F1 | 67506 | 55646 | -11860 |
| page_18 | F2 | 67458 | 55598 | -11860 |
| page_18 | F3 | 52655 | 41628 | -11027 |
| page_21 | F0 | 4454 | 3427 | -1027 |
| page_21 | F1 | 5655 | 4575 | -1080 |
| page_21 | F2 | 5631 | 4551 | -1080 |
| page_21 | F3 | 4070 | 3074 | -996 |
| page_22 | F0 | 28791 | 28233 | -558 |
| page_22 | F1 | 36973 | 36412 | -561 |
| page_22 | F2 | 36916 | 36356 | -560 |
| page_22 | F3 | 23190 | 22674 | -516 |
| page_23 | F0 | 13328 | 11920 | -1408 |
| page_23 | F1 | 15065 | 13555 | -1510 |
| page_23 | F2 | 15027 | 13517 | -1510 |
| page_23 | F3 | 11788 | 10394 | -1394 |
| page_24 | F0 | 12388 | 8190 | -4198 |
| page_24 | F1 | 14258 | 9777 | -4481 |
| page_24 | F2 | 14218 | 9737 | -4481 |
| page_24 | F3 | 11050 | 7150 | -3900 |

Cells file for the sensitivity run: `experiments/results/revision1/consistent_cells.json` (24 cells).

Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: 120 SHA-256 equal.
