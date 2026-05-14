# Fix dataclasses.replace bug in Feishu topic threading

## Description

This PR fixes a critical bug in the Feishu platform adapter that prevents topic/thread branching from working correctly.

### Bug Details

**Error**: `AttributeError: 'SessionSource' object has no attribute 'replace'`

**Location**: `gateway/platforms/feishu.py:3023`

**Root Cause**: The code incorrectly calls `source.replace(thread_id=None)` as an instance method, but `dataclasses.replace()` is a module function that should be called as `replace(source, thread_id=None)`.

### Changes

1. **Import fix** (line 63): Add `replace` to the imports from `dataclasses`
   ```python
   from dataclasses import dataclass, field, replace
   ```

2. **Method call fix** (line 3023): Change instance method call to module function call
   ```python
   # Before (incorrect):
   main_source = source.replace(thread_id=None)

   # After (correct):
   main_source = replace(source, thread_id=None)
   ```

### Impact

This bug completely breaks the topic/thread branching feature in Feishu private chats. When users create a topic by replying to a message, the bot cannot properly route sessions to the new topic thread.

### Testing

The fix has been tested in production:
- Verified with "烧菜" (cooking) topic scenario
- Hermes successfully receives and processes messages from topics
- Thread information (thread_id, root_id, parent_id) is correctly extracted
- Sidecar plugin (hermes-feishu-streaming-card) successfully sends cards to topics

### Compatibility

- **No breaking changes**: This is a pure bug fix
- **Backward compatible**: Existing functionality remains unchanged
- **Python version**: Compatible with all supported Python versions (3.9+)

## Related

This bug was discovered while developing the `hermes-feishu-streaming-card` plugin's thread routing feature (v3.5.0). The plugin successfully extracts thread information, but Hermes's internal topic branching logic fails without this fix.

## Patch

```diff
diff --git a/gateway/platforms/feishu.py b/gateway/platforms/feishu.py
--- a/gateway/platforms/feishu.py
+++ b/gateway/platforms/feishu.py
@@ -60,7 +60,7 @@
 import threading
 import time
 import uuid
 from collections import OrderedDict
-from dataclasses import dataclass, field
+from dataclasses import dataclass, field, replace
 from datetime import datetime
 from pathlib import Path
 from types import SimpleNamespace
@@ -3017,7 +3017,7 @@
             return  # Already has content — nothing to do
 
         # Build the main-chat source (same chat, no thread)
-        main_source = source.replace(thread_id=None)
+        main_source = replace(source, thread_id=None)
         main_session_key = build_session_key(main_source)
         main_entry = self._session_store.get_or_create_session(main_source)
```

## Checklist

- [x] Bug identified and root cause analyzed
- [x] Minimal fix implemented (2 lines changed)
- [x] Fix tested in production environment
- [x] No breaking changes
- [x] Patch file provided for easy application

## Author

Discovered and fixed by @hutao562 while developing [hermes-feishu-streaming-card](https://github.com/hutao562/hermes-feishu-streaming-card) v3.5.0.
