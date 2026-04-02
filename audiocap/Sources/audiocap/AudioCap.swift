import ArgumentParser
import Foundation

@main
struct AudioCap: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Capture system audio and microphone for Minuta"
    )

    @Option(name: .long, help: "Unix socket path for communication")
    var socket: String = "/tmp/minuta.sock"

    @Option(name: .long, help: "Audio sample rate in Hz")
    var sampleRate: Int = 16000

    @Flag(name: .long, help: "Disable microphone capture")
    var noMic: Bool = false

    @Flag(name: .long, help: "Disable system audio capture")
    var noSystem: Bool = false

    func run() async throws {
        print("[audiocap] Starting audio capture...")
        print("[audiocap] Socket: \(socket)")
        print("[audiocap] Sample rate: \(sampleRate) Hz")
        print("[audiocap] Microphone: \(!noMic), System audio: \(!noSystem)")

        // Connect to Python backend via Unix socket
        let client = SocketClient(socketPath: socket)
        do {
            try client.connect()
        } catch {
            print("[audiocap] Failed to connect to socket: \(error)")
            print("[audiocap] Make sure the Minuta backend is running")
            throw ExitCode.failure
        }

        // Start heartbeat
        client.startHeartbeat()

        // Start audio capture
        let capture = AudioCapture(
            socketClient: client,
            sampleRate: sampleRate,
            captureMic: !noMic,
            captureSystem: !noSystem
        )

        do {
            try await capture.start()
        } catch {
            print("[audiocap] Failed to start capture: \(error)")
            client.disconnect()
            throw ExitCode.failure
        }

        // Handle SIGINT/SIGTERM for graceful shutdown
        let signalSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
        signal(SIGINT, SIG_IGN)
        signalSource.setEventHandler {
            print("\n[audiocap] Shutting down...")
            capture.stop()
            client.disconnect()
            Foundation.exit(0)
        }
        signalSource.resume()

        let termSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        signal(SIGTERM, SIG_IGN)
        termSource.setEventHandler {
            capture.stop()
            client.disconnect()
            Foundation.exit(0)
        }
        termSource.resume()

        // Keep running
        print("[audiocap] Capturing audio... Press Ctrl+C to stop.")
        while true {
            try await Task.sleep(for: .seconds(3600))
        }
    }
}
