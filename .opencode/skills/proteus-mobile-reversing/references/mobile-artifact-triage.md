# Mobile Artifact Triage

Use this reference after extraction to choose high-signal mobile files.

## Safe Ingestion

- Treat every supplied archive as untrusted. Use the bundled extractor rather
  than direct `unzip` or `extractall` for the first pass.
- Keep the output outside directory inputs and use a fresh output directory for
  every run so stale evidence cannot be confused with current evidence.
- Do not increase file-count, expanded-size, per-file, or compression-ratio
  limits without recording why the artifact legitimately needs the override.
- For XAPK/APKS, preserve which split APK supplied each file. For AAB, preserve
  the module-relative path.
- Keep hashes and tool failures in the evidence manifest. A missing or failed
  tool is a limitation, not permission to infer its expected output.

## Mobile Context Evidence

Continue as mobile only when there is concrete project or artifact evidence.

- Android evidence: `AndroidManifest.xml`, Gradle Android plugin files,
  `app/src/main`, Android resources/assets, APK/AAB/XAPK, DEX, JNI, `.so`,
  React Native Android, Flutter Android, Capacitor/Cordova Android.
- iOS evidence: `.xcodeproj`, `.xcworkspace`, `Podfile`, iOS `Package.swift`,
  `Info.plist`, `.entitlements`, IPA, `.app`, Mach-O, Frameworks, Swift or
  Objective-C app code, React Native iOS, Flutter iOS, Capacitor/Cordova iOS.

If the repository only contains backend or web code plus mobile API references,
route back to the Proteus coordinator instead of forcing mobile analysis.

## APK/AAB/XAPK

- Review `AndroidManifest.xml` for exported activities, services, receivers,
  providers, permissions, custom schemes, app links, backup settings, network
  security config, debuggable state, and cleartext policy.
- Review resources for endpoints, feature flags, OAuth/client IDs, certificate
  pins, cloud project identifiers, and remote config keys.
- Review DEX/decompiled code for WebViews, deeplinks, file providers,
  downloads, update logic, crypto, authentication, storage, IPC, root/debug
  checks, TLS handling, and JNI load/call sites.

## React Native Bundle

- Locate files under `assets/` named like `index.android.bundle`,
  `index.bundle`, `*.hbc`, or `*.bundle`.
- Plain JS bundles are readable text and usually include module wrappers,
  endpoint strings, route names, feature flags, and library identifiers.
- Hermes bytecode needs a Hermes-aware tool for reliable decompilation. If no
  Hermes tool is available, extract strings and metadata only and mark the
  limitation.
- Prioritize modules handling auth, API clients, storage, deeplinks, WebView
  bridges, native module calls, crypto, and update mechanisms.

## Native Libraries

- Group `.so` files by ABI (`arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`).
- Collect `file`, `readelf -h`, `readelf -d`, `readelf -Ws`, `objdump -T`,
  `nm -D`, and `strings` output when tools are installed.
- Look for JNI exports (`Java_*`, `JNI_OnLoad`), crypto, serialization,
  compression, custom parsers, update/install code, filesystem access,
  networking, command execution, and dynamic loading.
- Connect native behavior back to Java/Kotlin or React Native callsites before
  claiming exploitability.

## iOS/IPA/App

- Review `Info.plist` for URL schemes, ATS exceptions, background modes,
  document types, app groups, associated domains, and sensitive permissions.
- Review entitlements for keychain access groups, app groups, associated
  domains, push, iCloud, VPN, network extensions, and debug/task allowances.
- Review Mach-O binaries and Frameworks with `otool`, `nm`, `strings`, `lipo`,
  `codesign`, and `swift-demangle` when available.
- Prioritize WebViews, custom URL schemes, universal links, pasteboard,
  keychain/storage, jailbreak/debug checks, TLS/pinning, crypto, update logic,
  native bridge calls, and Objective-C/Swift exposed selectors.

## Evidence Standard

- Prefer file path plus symbol/function/module plus surrounding code or string.
- Separate "interesting" from "reachable" and "security-impacting".
- Record tool gaps explicitly; do not turn incomplete decompilation into a
  stronger claim.
