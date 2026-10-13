import Combine
import Foundation

@MainActor
final class OverviewStore: ObservableObject {
    @Published private(set) var overview: MobileOverview?
    @Published private(set) var isLoading = false
    @Published private(set) var lastRefresh: Date?
    @Published var errorMessage: String?

    private let api = EMSAPIClient()

    func refresh(baseURLText: String) async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            overview = try await api.fetchOverview(baseURLText: baseURLText)
            lastRefresh = Date()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

func amsterdamDeadlineText(_ date: Date) -> String {
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = TimeZone(identifier: "Europe/Amsterdam")
    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm"
    return formatter.string(from: date)
}

func amsterdamDeadlineDate(_ value: String?) -> Date? {
    guard let value, !value.isEmpty else { return nil }
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = TimeZone(identifier: "Europe/Amsterdam")
    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm"
    return formatter.date(from: value)
}
