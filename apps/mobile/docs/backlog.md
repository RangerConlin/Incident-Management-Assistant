# Backlog

## Firebase Android app package alignment

- Priority: Medium
- Area: Android release / Firebase Cloud Messaging
- Status: Backlog

The Play Store package name is now `com.icscommand.sarapp`, but the Firebase Android app configuration was originally generated for `com.icscommand.ics_mobile_app`. The local `android/app/google-services.json` package field has been adjusted so release builds can proceed, but this should be replaced with an official Firebase-generated config for the new package.

Tasks:

- Add/register Android app `com.icscommand.sarapp` in the Firebase project `sarapp-mobile-companion`.
- Download the updated `google-services.json` from Firebase.
- Replace `android/app/google-services.json` with the official file.
- Regenerate or verify `lib/firebase_options.dart` with FlutterFire so Android uses the matching Firebase app id.
- Smoke test Firebase initialization and FCM token registration on Android.

Reason: push notification delivery and Firebase app identity should use the same package name as the Play Store app before relying on production FCM behavior.
