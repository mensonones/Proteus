---
name: proteus-mobile-reversing
description: "Mobile-only reversing and vulnerability research for Proteus. Use when the task involves Android or iOS projects/artifacts, APK/AAB/XAPK/IPA/app bundles, React Native index.bundle or Hermes bytecode, native .so or Mach-O libraries, JNI/native bridges, mobile app storage/network/auth/WebView/deeplink flows, decompilation, static triage, or mobile-focused attack surface. When selected, first decide whether the context is mobile; continue only with concrete mobile evidence, use installed reverse-engineering tools first, cover the known mobile baseline, then propose non-obvious mobile-specific hypotheses with cheap validation experiments."
---

# Proteus Mobile Reversing

Use this skill for mobile app research only. First decide whether the provided
context is actually mobile. Continue only when Android/iOS project files,
mobile build metadata, or mobile binary artifacts are present. Keep the
investigation centered on APK/AAB/IPA/app contents, React Native or Hermes
bundles, native libraries, manifests/plists/entitlements, resources, app
storage, network behavior, and mobile runtime boundaries.

Follow the Proteus base research contract. Do not drift into web/backend
research unless a mobile artifact proves that the mobile client reaches that
surface and the next step is required to validate the mobile finding.

This is a tactical skill, not a Proteus role/subagent contract. The coordinator
may invoke it directly, or a host assistant may inline it into a delegated
mobile-focused task. In either case, the mobile work must operate in two passes:

1. Known mobile baseline: cover the established Android/iOS reversing and
   vulnerability surfaces that a competent mobile review should not miss.
2. Exploratory mobile hypotheses: generate non-obvious, mobile-specific
   hypotheses that are plausible under the target's actual artifacts, then
   define the smallest experiment or evidence check that would kill or promote
   each one.

Do not let the baseline become a checklist-only review. Use known classes to
anchor coverage, then ask whether the mobile context changes the attack shape:
intermittent connectivity, background lifecycle, one-handed and partial flows,
OS-mediated intents/links/shares, clipboard/pasteboard, notification actions,
widgets/shortcuts, biometric or device-bound state, app restore/backup,
multi-account state, embedded web/native bridge transitions, local cache
authority, offline queues, feature flags, staged rollout behavior, and
platform-specific permission or entitlement drift.

## Operating Method

1. State the target-context decision: `mobile`, `mixed-mobile-entry`, or
   `not-mobile`. If `not-mobile`, stop and route back to the Proteus
   coordinator.
2. State the mobile artifact and target platform: Android project, iOS project,
   APK, AAB, XAPK, IPA, `.app`, extracted app directory, `index.bundle`, Hermes
   bytecode, `.so`, Mach-O, DEX, or mixed artifact.
3. Check tool availability with `scripts/mobile_toolchain.py --check --json
   --versions`. Select only the profiles relevant to the artifact. Use installed
   tools when present. If a missing tool is materially useful, ask for approval
   to install it or run `scripts/mobile_toolchain.py --install ...` with the
   narrowest useful profile.
4. Extract and index artifacts with `scripts/extract_mobile_artifacts.py` when
   the input is an APK, AAB, ZIP, XAPK, APKS, IPA, `.app`, or directory. Always
   use a fresh output directory outside a directory input. Keep the default
   archive safety limits unless the artifact requires a reviewed, explicit
   override. The extractor handles nested XAPK/APKS APKs, inventories DEX and
   high-signal resources, and runs available decompiler/native tools unless
   `--no-tools` is supplied.
5. Triage high-signal files first: `AndroidManifest.xml`, `Info.plist`,
   entitlements, DEX/decompiled Java or Kotlin, Swift/Objective-C code,
   `assets/index.*bundle`, Hermes bytecode, `.so` exports/imports, Mach-O
   symbols/imports, native strings, network config, embedded secrets, deep
   links/universal links, WebViews, update/download code, crypto, auth, storage,
   IPC, URL schemes, and JNI/native bridges.
6. For React Native, identify whether the bundle is plain JS or Hermes bytecode.
   Use Hermes tools when available; otherwise extract strings and module names,
   then report the limitation clearly.
7. For `.so` files and Mach-O binaries, identify architecture, hardening,
   exported JNI/native symbols, dynamic imports, risky native APIs, embedded
   endpoints/secrets, and Java/Kotlin/Swift/Objective-C/React Native callsites
   that load or invoke the native code.
8. Separate known-baseline observations from exploratory hypotheses. For each
   exploratory hypothesis, include why it is non-obvious, what mobile behavior
   makes it plausible, a cheap validation experiment, and kill criteria.
9. Build candidate findings only from reachable mobile behavior. Tie each claim
   to a file, symbol, route, manifest entry, exported component, bundle module,
   or native function.
10. Route credible exploitability work to `proteus-poc-exploit`; route broader research
   expansion to `proteus-chaining` only after the mobile entry point is concrete.

## Tooling Policy

Prefer these tools if installed:

- APK/AAB: `jadx`, `apktool`, `bundletool`, `aapt`, `apksigner`, `zipinfo`,
  `unzip`.
- iOS/IPA: `plutil`, `otool`, `nm`, `strings`, `lipo`, `codesign`,
  `swift-demangle`, `class-dump`, `ipsw`, `macho2json`.
- React Native/Hermes: `hermes-dec`, `hbctool`, `hbc-disassembler`,
  `hermes`, `node`, `strings`.
- Native `.so`: `file`, `readelf`, `objdump`, `nm`, `strings`, `rabin2`,
  `radare2`, `ghidra`, `ghidra-analyzeHeadless`, `checksec`.
- Dynamic/mobile runtime when explicitly needed: `adb`, `frida`,
  `frida-trace`, `objection`, `mitmproxy`.
- Network routing for dynamic analysis: route traffic through
  Tor/Proxychains (`ALL_PROXY=socks5://localhost:9050` or `proxychains4`)
  unless the mobile target requires direct interception via mitmproxy.

Do not silently install tooling. If installation is needed, state exactly which
tool and why. Prefer package-manager installs for standard tools and isolated
tool installs (`pipx`, virtualenv, npm global only when appropriate) for
reversing utilities. If installation fails or is not approved, continue with
available static evidence and mark the gap.

## Bundled Scripts

- `scripts/mobile_toolchain.py`: detect installed tools, versions, and profile
  capabilities as text or JSON. Supported profiles are `core`, `android`,
  `ios`, `rn`, `native`, and `dynamic`; installation remains approval-gated and
  is offered only where a reliable recipe exists.
- `scripts/extract_mobile_artifacts.py`: safely unpack APK/AAB/XAPK/APKS/IPA/ZIP
  inputs, reject traversal/symlinks/suspicious expansion, inventory DEX,
  manifests, resources, bundles and native files, run available static tools,
  and generate a unified `manifest.json` plus a text triage report.

Read `references/mobile-artifact-triage.md` when deciding which extracted files
to prioritize or how to interpret tool output.

## Anti-Patterns

- Do not analyze the backend as the primary target just because URLs appear in
  the app.
- Do not report embedded values as secrets until context proves sensitivity,
  reachability, and impact.
- Do not claim Hermes decompilation quality when only strings were extracted.
- Do not treat a native crash, unsafe function, or exported symbol as exploitable
  without a reachable Java/JNI or app-input path.
- Do not run dynamic testing against real services without explicit scope and
  authorization.

Required output:

```json
{
  "contextDecision": "mobile|mixed-mobile-entry|not-mobile",
  "mobileScope": "android-project|ios-project|apk|aab|xapk|ipa|app|bundle|hermes|native-so|macho|mixed|not-mobile",
  "artifactsReviewed": [],
  "toolsUsed": [],
  "toolsMissing": [],
  "reactNativeBundle": {
    "present": false,
    "format": "plain-js|hermes|unknown|not-found",
    "evidence": []
  },
  "nativeLibraries": [],
  "iosArtifacts": [],
  "mobileAttackSurface": [],
  "knownBaseline": [],
  "exploratoryHypotheses": [
    {
      "hypothesis": "",
      "whyNonObvious": "",
      "mobileSpecificReasoning": "",
      "cheapValidationExperiment": "",
      "killCriteria": "",
      "expectedEvidence": []
    }
  ],
  "validationExperiments": [],
  "candidateFindings": [],
  "limitations": [],
  "nextProteusRoute": "continue-mobile|send-to-chaining|send-to-poc|blocked",
  "contractSignature": {}
}
```

Before returning, delete any extracted APK/IPA directories, temporary
decompilation output, and tool-generated artifacts created during this
front unless they are gated as durable evidence for the next step.
