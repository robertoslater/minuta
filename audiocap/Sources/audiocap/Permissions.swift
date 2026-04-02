import AVFoundation
import ScreenCaptureKit

/// Check and request required macOS permissions.
enum Permissions {

    /// Check microphone permission.
    static func checkMicrophone() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .audio)
        default:
            print("[audiocap] Microphone permission denied.")
            print("[audiocap] Grant access in: System Settings > Privacy & Security > Microphone")
            return false
        }
    }

    /// Check screen recording permission (required for system audio via ScreenCaptureKit).
    static func checkScreenRecording() async -> Bool {
        do {
            // Attempting to get shareable content triggers the permission prompt
            _ = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
            return true
        } catch {
            print("[audiocap] Screen Recording permission required for system audio capture.")
            print("[audiocap] Grant access in: System Settings > Privacy & Security > Screen Recording")
            return false
        }
    }
}
