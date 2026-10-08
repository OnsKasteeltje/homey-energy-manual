import Foundation

enum EMSAPIError: LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case httpStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "Ongeldige EMS API URL."
        case .invalidResponse:
            return "Geen geldige response van de EMS API."
        case .httpStatus(let status):
            return "EMS API gaf HTTP status \(status)."
        }
    }
}

struct EMSAPIClient {
    func fetchOverview(baseURLText: String) async throws -> MobileOverview {
        guard let baseURL = URL(string: baseURLText.trimmingCharacters(in: .whitespacesAndNewlines)),
              let url = URL(string: "/api/mobile/v1/overview", relativeTo: baseURL)?.absoluteURL
        else {
            throw EMSAPIError.invalidBaseURL
        }

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
