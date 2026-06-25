# Owner Android QA Checklist

## Authentication

1. Install app.
2. Login with owner test account.
3. Close app.
4. Remove app from recent apps.
5. Reopen app.
6. Verify session is still active.
7. Logout.
8. Login again.

## PO Workflow

1. Create a simple PO from mobile.
2. Verify fabric-available scenario.
3. Verify fabric-shortage scenario.
4. Move a fabric-ready PO to next stage.
5. Complete a stage with partial quantity.
6. Edit one historical May PO.
7. Edit one historical June PO.
8. Dispatch partial quantity.
9. Confirm remaining quantity is visible.

## AI

1. Ask first text question.
2. Ask second text question immediately.
3. Ask first voice question.
4. Ask second voice question.
5. Try write-action command.
6. Confirm preview appears.
7. Confirm action.
8. Verify database/page changed.
9. Confirm spoken response plays.
10. Stop speech and ask another question.

## PDF

1. Generate a PDF.
2. Download PDF.
3. Open PDF on Android.
4. Share PDF if Android share sheet is available.
5. Close and reopen app.
6. Confirm report remains available.

## Android Behavior

1. Test on Wi-Fi.
2. Test on mobile data.
3. Deny microphone permission and confirm graceful error.
4. Grant microphone permission and retest voice.
5. Deny notification permission and confirm app still works.
6. Grant notification permission.
7. Check Android keyboard does not cover input.
8. Press Android back button from mobile screens.
9. Turn network off and confirm offline error.
10. Restore network and confirm recovery.
