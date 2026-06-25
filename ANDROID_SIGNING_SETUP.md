# Android Signing Setup

No existing secure release keystore was found during release preparation, so only a debug APK can be built automatically.

Do not lose the release keystore once created. Android updates must be signed with the same keystore.

## Generate Keystore

Run this locally and store the file outside Git:

```bash
mkdir -p deployment_private/android
keytool -genkeypair \
  -v \
  -keystore deployment_private/android/factory-control-owner-test.jks \
  -alias factory-control-owner-test \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Use strong passwords and keep them private.

## Configure Gradle Signing

Copy:

```bash
cp frontend/android/keystore.properties.example frontend/android/keystore.properties
```

Edit `frontend/android/keystore.properties` locally. Never commit it.

## Build Release APK

After signing config is wired into Gradle:

```bash
cd frontend/android
./gradlew assembleRelease
```

Verify signature if Android build tools are available:

```bash
apksigner verify --verbose app/build/outputs/apk/release/app-release.apk
```
