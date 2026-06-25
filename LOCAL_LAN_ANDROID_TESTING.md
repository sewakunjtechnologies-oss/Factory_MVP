# Local LAN Android Testing

Use this only for temporary testing when the Android phone and laptop are on the same Wi-Fi.

## 1. Find Laptop LAN IP

```bash
scripts/show_lan_ip.sh
```

Example:

```text
192.168.1.10
```

## 2. Configure Frontend

Copy:

```bash
cp frontend/.env.android.local.example frontend/.env.production
```

Edit:

```text
VITE_API_BASE_URL=http://<LAPTOP_LAN_IP>:8000
VITE_ALLOW_LOCAL_HTTP=true
```

## 3. Run Backend on Laptop

```bash
docker compose up --build
```

Or run the FastAPI backend directly on `0.0.0.0:8000`.

## 4. Build Local Android APK

```bash
cd frontend
npm run android:build:local
cd android
./gradlew assembleDebug -PallowCleartext
```

## Notes

- Laptop and phone must be on the same Wi-Fi.
- Firewall must allow inbound connections to port 8000.
- This will not work outside the local network.
- HTTP cleartext is only acceptable for short local testing.
- Cloud testing should use HTTPS and `npm run android:build:cloud`.
