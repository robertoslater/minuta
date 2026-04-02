// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "audiocap",
    platforms: [
        .macOS(.v13)  // macOS 13+ for ScreenCaptureKit audio
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.3.0"),
    ],
    targets: [
        .executableTarget(
            name: "audiocap",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
            ],
            linkerSettings: [
                .linkedFramework("ScreenCaptureKit"),
                .linkedFramework("AVFoundation"),
                .linkedFramework("CoreAudio"),
            ]
        ),
    ]
)
