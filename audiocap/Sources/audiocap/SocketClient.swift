import Foundation

/// Unix domain socket client using POSIX sockets for reliability.
class SocketClient {
    private let socketPath: String
    private var fd: Int32 = -1
    private let lock = NSLock()
    var isConnected: Bool { fd >= 0 }

    init(socketPath: String) {
        self.socketPath = socketPath
    }

    func connect() throws {
        fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else {
            throw SocketError.createFailed(errno: errno)
        }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        socketPath.withCString { ptr in
            withUnsafeMutablePointer(to: &addr.sun_path) { pathPtr in
                let bound = pathPtr.withMemoryRebound(to: CChar.self, capacity: 104) { dest in
                    strlcpy(dest, ptr, 104)
                }
            }
        }

        let addrLen = socklen_t(MemoryLayout<sockaddr_un>.size)
        let result = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                Foundation.connect(fd, sockPtr, addrLen)
            }
        }

        guard result == 0 else {
            close(fd)
            fd = -1
            throw SocketError.connectFailed(errno: errno)
        }

        print("[audiocap] Connected to socket: \(socketPath)")
    }

    func send(_ data: Data) {
        guard fd >= 0 else { return }
        lock.lock()
        defer { lock.unlock() }

        data.withUnsafeBytes { ptr in
            guard let baseAddr = ptr.baseAddress else { return }
            var sent = 0
            let total = data.count
            while sent < total {
                let n = Foundation.write(fd, baseAddr + sent, total - sent)
                if n <= 0 {
                    print("[audiocap] Socket write error")
                    break
                }
                sent += n
            }
        }
    }

    func disconnect() {
        if fd >= 0 {
            close(fd)
            fd = -1
        }
    }

    /// Start heartbeat loop.
    func startHeartbeat(interval: TimeInterval = 5.0) {
        Task {
            while isConnected {
                send(encodeHeartbeat())
                try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
            }
        }
    }
}

enum SocketError: Error, LocalizedError {
    case createFailed(errno: Int32)
    case connectFailed(errno: Int32)

    var errorDescription: String? {
        switch self {
        case .createFailed(let e): return "Failed to create socket: \(String(cString: strerror(e)))"
        case .connectFailed(let e): return "Failed to connect: \(String(cString: strerror(e)))"
        }
    }
}
