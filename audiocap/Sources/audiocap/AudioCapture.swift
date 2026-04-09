import AVFoundation
import CoreAudio
import Foundation
import ScreenCaptureKit

/// Captures system audio via ScreenCaptureKit and microphone via AVAudioEngine.
/// Sends PCM float32 16kHz mono data to the Python backend via Unix socket.
class AudioCapture: NSObject {
    private let socketClient: SocketClient
    private let sampleRate: Int
    private let captureMic: Bool
    private let captureSystem: Bool

    // Microphone
    private var audioEngine: AVAudioEngine?

    // System audio (ScreenCaptureKit)
    private var scStream: SCStream?
    private var streamOutput: AudioStreamOutput?

    init(socketClient: SocketClient, sampleRate: Int, captureMic: Bool, captureSystem: Bool) {
        self.socketClient = socketClient
        self.sampleRate = sampleRate
        self.captureMic = captureMic
        self.captureSystem = captureSystem
        super.init()
    }

    func start() async throws {
        // Send metadata
        socketClient.send(encodeMetadata([
            "source": "audiocap",
            "sample_rate": sampleRate,
            "channels": 1,
            "format": "float32",
            "capture_mic": captureMic,
            "capture_system": captureSystem,
        ]))

        if captureMic {
            try startMicrophone()
        }
        if captureSystem {
            do {
                try await startSystemAudio()
            } catch {
                print("[audiocap] System audio capture failed (Screen Recording permission needed): \(error.localizedDescription)")
                print("[audiocap] Continuing with microphone only")
            }
        }

        // At least one source must work
        guard audioEngine != nil || scStream != nil else {
            throw AudioCaptureError.permissionDenied("No audio source available")
        }

        print("[audiocap] Audio capture started (mic: \(audioEngine != nil), system: \(scStream != nil))")
    }

    func stop() {
        // Stop microphone
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine = nil

        // Stop system audio
        scStream?.stopCapture()
        scStream = nil

        print("[audiocap] Audio capture stopped")
    }

    // MARK: - Microphone Capture

    private func startMicrophone() throws {
        let engine = AVAudioEngine()
        let inputNode = engine.inputNode
        let nativeFormat = inputNode.outputFormat(forBus: 0)

        print("[audiocap] Mic native format: \(nativeFormat)")

        // Send metadata with actual sample rate so Python can resample
        socketClient.send(encodeMetadata([
            "mic_sample_rate": Int(nativeFormat.sampleRate),
            "mic_channels": Int(nativeFormat.channelCount),
        ]))

        // Tap in native format - send raw PCM, let Python resample
        inputNode.installTap(onBus: 0, bufferSize: 4800, format: nativeFormat) { [weak self] buffer, _ in
            guard let self = self,
                  let channelData = buffer.floatChannelData,
                  buffer.frameLength > 0 else { return }

            // Send first channel only (mono)
            let data = Data(
                bytes: channelData[0],
                count: Int(buffer.frameLength) * MemoryLayout<Float>.size
            )
            self.socketClient.send(encodeAudioFrame(pcmData: data, source: "mic"))
        }

        engine.prepare()
        try engine.start()
        self.audioEngine = engine
        print("[audiocap] Microphone capture started")
    }

    // MARK: - System Audio Capture (ScreenCaptureKit)

    private func startSystemAudio() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)

        guard let display = content.displays.first else {
            throw AudioCaptureError.noDisplay
        }

        let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])

        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.excludesCurrentProcessAudio = true
        config.sampleRate = sampleRate
        config.channelCount = 1

        // Minimize video overhead (we only want audio)
        config.width = 2
        config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)  // 1 FPS max

        let output = AudioStreamOutput(socketClient: socketClient, sampleRate: sampleRate)
        self.streamOutput = output

        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        try stream.addStreamOutput(output, type: .audio, sampleHandlerQueue: .global(qos: .userInteractive))

        try await stream.startCapture()
        self.scStream = stream
        print("[audiocap] System audio capture started via ScreenCaptureKit")
    }
}

// MARK: - ScreenCaptureKit Audio Output

class AudioStreamOutput: NSObject, SCStreamOutput {
    private let socketClient: SocketClient
    private let sampleRate: Int

    init(socketClient: SocketClient, sampleRate: Int) {
        self.socketClient = socketClient
        self.sampleRate = sampleRate
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio else { return }
        guard let blockBuffer = sampleBuffer.dataBuffer else { return }

        let length = CMBlockBufferGetDataLength(blockBuffer)
        var data = Data(count: length)
        data.withUnsafeMutableBytes { ptr in
            CMBlockBufferCopyDataBytes(blockBuffer, atOffset: 0, dataLength: length, destination: ptr.baseAddress!)
        }

        socketClient.send(encodeAudioFrame(pcmData: data, source: "system"))
    }
}

// MARK: - Errors

enum AudioCaptureError: Error, LocalizedError {
    case formatError(String)
    case noDisplay
    case permissionDenied(String)

    var errorDescription: String? {
        switch self {
        case .formatError(let msg): return "Audio format error: \(msg)"
        case .noDisplay: return "No display found for system audio capture"
        case .permissionDenied(let msg): return "Permission denied: \(msg)"
        }
    }
}
