import Foundation

/// Wire protocol message types for Unix socket communication.
enum MessageType: UInt8 {
    case audioChunk = 0x01
    case control = 0x02
    case metadata = 0x03
    case error = 0x04
    case heartbeat = 0xFF
}

/// Encodes a frame for the wire protocol.
/// Format: [4 bytes: payload length, big-endian] [1 byte: message type] [N bytes: payload]
func encodeFrame(type: MessageType, payload: Data) -> Data {
    var frame = Data(capacity: 5 + payload.count)
    var length = UInt32(payload.count).bigEndian
    frame.append(Data(bytes: &length, count: 4))
    frame.append(type.rawValue)
    frame.append(payload)
    return frame
}

/// Encode an audio chunk frame with source tag.
func encodeAudioFrame(pcmData: Data, source: String) -> Data {
    // Prepend source tag: 1 byte length + source string + PCM data
    let sourceData = source.data(using: .utf8) ?? Data()
    var payload = Data(capacity: 1 + sourceData.count + pcmData.count)
    payload.append(UInt8(sourceData.count))
    payload.append(sourceData)
    payload.append(pcmData)
    return encodeFrame(type: .audioChunk, payload: payload)
}

/// Encode a metadata frame.
func encodeMetadata(_ dict: [String: Any]) -> Data {
    let jsonData = try! JSONSerialization.data(withJSONObject: dict)
    return encodeFrame(type: .metadata, payload: jsonData)
}

/// Encode a control frame.
func encodeControl(_ dict: [String: Any]) -> Data {
    let jsonData = try! JSONSerialization.data(withJSONObject: dict)
    return encodeFrame(type: .control, payload: jsonData)
}

/// Encode an error frame.
func encodeError(code: String, message: String) -> Data {
    let dict: [String: Any] = ["code": code, "message": message]
    let jsonData = try! JSONSerialization.data(withJSONObject: dict)
    return encodeFrame(type: .error, payload: jsonData)
}

/// Encode a heartbeat frame.
func encodeHeartbeat() -> Data {
    return encodeFrame(type: .heartbeat, payload: Data())
}
