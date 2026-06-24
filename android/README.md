# Android APK wrapper

이 디렉터리는 `Village RP Engine`을 Android APK로 감싸기 위한 최소 WebView + Chaquopy 프로젝트다.

구조:
- Android `WebView` 앱
- Chaquopy로 Python 런타임 내장
- 앱 시작 시 내장 Python이 `web_ui.run_server()`를 `127.0.0.1:8000`에서 실행
- WebView가 해당 localhost UI를 로드

빌드 전제:
- Android Studio 최신 안정판
- JDK 17
- Android SDK Platform 35
- Gradle sync 가능 환경

빌드:
1. Android Studio에서 `android/` 폴더를 프로젝트로 연다.
2. 첫 sync 후 `app` 모듈을 선택한다.
3. `Build > Build Bundle(s) / APK(s) > Build APK(s)` 실행.

주의:
- 디버그 APK는 `android/app/build/outputs/apk/debug/app-debug.apk`로 생성된다.
- 저장 슬롯은 Android 앱 내부 저장소의 `files/saves` 아래에 생성된다.
