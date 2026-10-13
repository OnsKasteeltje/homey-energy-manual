import Foundation

enum EMSAPIError: LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case httpStatus(Int)
    case server(String, Int)

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "Ongeldige EMS API URL."
        case .invalidResponse:
            return "Geen geldige response van de EMS API."
        case .httpStatus(let status):
            return "EMS API gaf HTTP status \(status)."
        case .server(let message, let status):
            return "EMS command API: \(message) (HTTP \(status))."
        }
    }
}

private func emsURL(baseURLText: String, path: String) throws -> URL {
    let text = baseURLText.trimmingCharacters(in: .whitespacesAndNewlines)
    guard let baseURL = URL(string: text),
          let scheme = baseURL.scheme?.lowercased(),
          ["http", "https"].contains(scheme),
          baseURL.host != nil,
          let url = URL(string: path, relativeTo: baseURL)?.absoluteURL
    else {
        throw EMSAPIError.invalidBaseURL
    }
    return url
}

struct EMSAPIClient {
    func fetchOverview(baseURLText: String) async throws -> MobileOverview {
        let url = try emsURL(
            baseURLText: baseURLText,
            path: "/api/mobile/v1/overview"
        )

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 8

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw EMSAPIError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw EMSAPIError.httpStatus(http.statusCode)
        }

        return try JSONDecoder().decode(MobileOverview.self, from: data)
    }
}

struct TeslaDeadlineClient {
    private struct WireRequest: Encodable {
        let active: Bool
        let deadline: String
        let currentSoc: Int?
        let targetSoc: Int?
        let maxA: Int
        let clientRequestId: String
    }

    private struct ErrorResponse: Decodable {
        let error: String?
    }

    func fetchCurrent(baseURLText: String) async throws -> TeslaDeadlineCurrentResponse {
        let url = try emsURL(
            baseURLText: baseURLText,
            path: "/web/commands/current"
        )

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 8

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw EMSAPIError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw EMSAPIError.httpStatus(http.statusCode)
        }

        return try JSONDecoder().decode(TeslaDeadlineCurrentResponse.self, from: data)
    }

    func submit(
        baseURLText: String,
        pin: String,
        submission: TeslaDeadlineSubmission,
        clientRequestId: UUID
    ) async throws -> TeslaDeadlineCommandResponse {
        let url = try emsURL(
            baseURLText: baseURLText,
            path: "/web/commands/tesla"
        )

        let payload = WireRequest(
            active: submission.active,
            deadline: submission.deadline,
            currentSoc: submission.currentSoc,
            targetSoc: submission.targetSoc,
            maxA: submission.maxA,
            clientRequestId: clientRequestId.uuidString
        )

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(pin, forHTTPHeaderField: "X-Tesla-Control-Pin")
        request.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw EMSAPIError.invalidResponse
        }

        guard (200...299).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(ErrorResponse.self, from: data).error)
                ?? "COMMAND_REJECTED"
            throw EMSAPIError.server(message, http.statusCode)
        }

        let decoded = try JSONDecoder().decode(TeslaDeadlineCommandResponse.self, from: data)
        guard decoded.ok else {
            throw EMSAPIError.invalidResponse
        }
        return decoded
    }
}
