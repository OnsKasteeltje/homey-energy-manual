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
