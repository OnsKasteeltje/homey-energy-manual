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

@MainActor
final class DeadlineStore: ObservableObject {
    @Published private(set) var current: TeslaDeadlineCommandState?
    @Published private(set) var isLoading = false
    @Published private(set) var isSubmitting = false
    @Published var statusMessage: String?
    @Published var errorMessage: String?

    private let client = TeslaDeadlineClient()
    private var retrySubmission: TeslaDeadlineSubmission?
    private var retryRequestId: UUID?

    func loadCurrent(baseURLText: String) async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            current = try await client.fetchCurrent(baseURLText: baseURLText).tesla
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func submit(
        currentSoc: Int,
        targetSoc: Int,
        deadline: Date,
        maxA: Int,
        baseURLText: String,
        pin: String
    ) async {
        guard !isSubmitting else { return }

        do {
            let submission = try validatedSubmission(
                currentSoc: currentSoc,
                targetSoc: targetSoc,
                deadline: deadline,
                maxA: maxA,
                pin: pin
            )
            await perform(
                submission: submission,
                baseURLText: baseURLText,
                pin: pin
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func cancel(baseURLText: String, pin: String) async {
        guard !isSubmitting else { return }

        do {
            try validatePIN(pin)
            await perform(
                submission: .cancel,
                baseURLText: baseURLText,
                pin: pin
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func perform(
        submission: TeslaDeadlineSubmission,
        baseURLText: String,
        pin: String
    ) async {
        isSubmitting = true
        defer { isSubmitting = false }

        let requestId: UUID
        if retrySubmission == submission, let existing = retryRequestId {
            requestId = existing
        } else {
            requestId = UUID()
            retrySubmission = submission
            retryRequestId = requestId
        }

        do {
            let response = try await client.submit(
                baseURLText: baseURLText,
                pin: pin,
                submission: submission,
                clientRequestId: requestId
            )

            current = try await client.fetchCurrent(baseURLText: baseURLText).tesla
            retrySubmission = nil
            retryRequestId = nil
            errorMessage = nil

            switch response.derivedState {
            case "UPDATED":
                statusMessage = submission.active
                    ? "Deadline verwerkt door de Pi."
                    : "Deadline geannuleerd op de Pi."
            case "ALREADY_ACCEPTED":
                statusMessage = "Deze opdracht was al door de Pi geaccepteerd."
            default:
                statusMessage = "Opdracht geaccepteerd; afgeleide deadline-status volgt."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func validatedSubmission(
        currentSoc: Int,
        targetSoc: Int,
        deadline: Date,
        maxA: Int,
        pin: String
    ) throws -> TeslaDeadlineSubmission {
        try validatePIN(pin)

        guard (0...99).contains(currentSoc) else {
            throw DeadlineInputError.currentSOC
        }
        guard (1...100).contains(targetSoc), targetSoc > currentSoc else {
            throw DeadlineInputError.targetSOC
        }
        guard (6...16).contains(maxA) else {
            throw DeadlineInputError.maxA
        }
        guard deadline.timeIntervalSinceNow > 60 else {
            throw DeadlineInputError.deadline
        }

        return .activate(
            currentSoc: currentSoc,
            targetSoc: targetSoc,
            deadline: amsterdamDeadlineText(deadline),
            maxA: maxA
        )
    }

    private func validatePIN(_ pin: String) throws {
        guard pin.trimmingCharacters(in: .whitespacesAndNewlines).count >= 8 else {
            throw DeadlineInputError.pin
        }
    }
}

enum DeadlineInputError: LocalizedError {
    case currentSOC
    case targetSOC
    case deadline
    case maxA
    case pin

    var errorDescription: String? {
        switch self {
        case .currentSOC:
            return "Huidige SOC moet tussen 0 en 99% liggen."
        case .targetSOC:
            return "Doel-SOC moet hoger zijn dan de huidige SOC en maximaal 100%."
        case .deadline:
            return "Kies een deadline die minstens één minuut in de toekomst ligt."
        case .maxA:
            return "Maximale laadstroom moet tussen 6 en 16 A liggen."
        case .pin:
            return "Sla eerst een geldige Tesla control-PIN op bij Instellingen."
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
