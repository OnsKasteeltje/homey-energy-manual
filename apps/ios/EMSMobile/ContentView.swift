import Foundation
import SwiftUI

struct ContentView: View {
    @StateObject private var store = OverviewStore()
    @StateObject private var deadlineStore = DeadlineStore()
    @AppStorage("emsBaseURL") private var baseURL = ""

    var body: some View {
        TabView {
            NavigationStack {
                OverviewScreen(baseURL: baseURL)
            }
            .tabItem { Label("Overzicht", systemImage: "house.fill") }

            NavigationStack {
                DeadlineScreen(baseURL: baseURL)
            }
            .tabItem { Label("Deadline", systemImage: "clock.fill") }

            NavigationStack {
                SystemScreen()
            }
            .tabItem { Label("Systeem", systemImage: "gearshape.2.fill") }

            NavigationStack {
                SettingsScreen(baseURL: $baseURL)
            }
            .tabItem { Label("Instellingen", systemImage: "slider.horizontal.3") }
        }
        .environmentObject(store)
        .environmentObject(deadlineStore)
        .task {
            if !baseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                await store.refresh(baseURLText: baseURL)
            }
        }
    }
}

private struct OverviewScreen: View {
    @EnvironmentObject private var store: OverviewStore
    let baseURL: String

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                if let overview = store.overview {
                    LiveHeader(overview: overview)
                    EnergyCard(overview: overview)
                    EVCard(overview: overview)
                    if effectiveHotWaterMode(overview) == "BOILER" {
                        HotWaterCard(overview: overview)
                    }
                    HeatingCard(overview: overview)

                    if overview.flex.status != "OK" {
                        FlexWarningCard(overview: overview)
                    }
                } else if store.isLoading {
                    ProgressView("EMS laden…")
                        .frame(maxWidth: .infinity, minHeight: 180)
                } else {
                    ContentUnavailableView(
                        "Geen EMS-data",
                        systemImage: "bolt.slash",
                        description: Text(store.errorMessage ?? (baseURL.isEmpty ? "Stel eerst de privé EMS API-URL in bij Instellingen." : "Ververs om opnieuw te proberen."))
                    )
                }
            }
            .padding()
        }
        .navigationTitle("Ons Kasteeltje")
        .refreshable {
            await store.refresh(baseURLText: baseURL)
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                if store.isLoading {
                    ProgressView()
                } else {
                    Button {
                        Task { await store.refresh(baseURLText: baseURL) }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
        }
        .safeAreaInset(edge: .bottom) {
            if let error = store.errorMessage, store.overview != nil {
                Text(error)
                    .font(.caption)
                    .padding(8)
                    .frame(maxWidth: .infinity)
                    .background(.red.opacity(0.15))
            }
        }
    }
}

private struct LiveHeader: View {
    let overview: MobileOverview

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 3) {
                Text("Energieoverzicht")
                    .font(.headline)
                Text("Bijgewerkt \(localTime(overview.generatedAt))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Label(
                isLive ? "Live" : "Verouderd",
                systemImage: isLive ? "circle.fill" : "exclamationmark.triangle.fill"
            )
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(isLive ? .green : .orange)
        }
    }

    private var isLive: Bool {
        (overview.energy.stateAgeSec ?? .infinity) <= 30 &&
        overview.energy.gridMeasurementValid == true
    }
}

private struct EnergyCard: View {
    let overview: MobileOverview

    var body: some View {
        EMSCard(title: "Energie", systemImage: "bolt.fill") {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(power(overview.energy.gridPowerW))
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text(gridLabel)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(power(overview.energy.pvPowerW))
                        .font(.title2.bold())
                    Text("PV")
                        .foregroundStyle(.secondary)
                }
            }

            Divider()

            HStack {
                Metric(label: "Import", value: power(overview.energy.gridImportW))
                Spacer()
                Metric(label: "Export", value: power(overview.energy.gridExportW))
                Spacer()
                Metric(label: "Overig huis", value: power(overview.energy.otherHouseLoadW))
            }
        }
    }

    private var gridLabel: String {
        if (overview.energy.gridExportW ?? 0) > 0 { return "Teruglevering" }
        if (overview.energy.gridImportW ?? 0) > 0 { return "Netimport" }
        return "Netto nul"
    }
}

private struct EVCard: View {
    let overview: MobileOverview

    var body: some View {
        EMSCard(title: "Elektrische auto", systemImage: "car.fill") {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(connectionText)
                        .font(.title3.bold())
                    Text(overview.ev.charging == true ? "Laadt" : "Laadt niet")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(overview.ev.need ?? "—")
                    .font(.subheadline.bold())
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.secondary.opacity(0.14), in: Capsule())
            }

            Divider()

            HStack {
                Metric(label: "Vermogen", value: power(overview.ev.powerW))
                Spacer()
                Metric(label: "Gevraagd", value: amps(overview.ev.requestedA))
                Spacer()
                Metric(
                    label: "Deadline",
                    value: overview.ev.deadlineActive == true ? "Actief" : "Geen"
                )
            }
        }
    }

    private var connectionText: String {
        overview.ev.connected == true ? "Verbonden" : "Niet verbonden"
    }
}

private struct HotWaterCard: View {
    let overview: MobileOverview

    var body: some View {
        EMSCard(title: "Warm water", systemImage: "drop.fill") {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Elektrische boiler")
                        .font(.title3.bold())
                    Text(overview.hotWater.boilerOn == true ? "Boiler aan" : "Boiler uit")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(overview.hotWater.action ?? "—")
                    .font(.subheadline.bold())
            }

            Divider()

            HStack {
                Metric(label: "Boiler", value: power(overview.hotWater.boilerPowerW))
                Spacer()
                Metric(
                    label: "Seizoensadvies",
                    value: overview.hotWater.seasonalAdvice?.data?.advice ?? "—"
                )
            }
        }
    }
}

private struct HeatingCard: View {
    let overview: MobileOverview

    var body: some View {
        EMSCard(title: "Verwarming", systemImage: "flame.fill") {
            Text(
                overview.heating.readyRooms.isEmpty
                ? "Geen actieve preheat-kandidaten"
                : overview.heating.readyRooms.joined(separator: ", ")
            )
            .font(.title3.bold())

            HStack {
                Metric(label: "Shadow grant", value: overview.heating.shadowGrant ?? "—")
                Spacer()
                Metric(
                    label: "Venster sluit",
                    value: overview.heating.earliestOpportunityClosesAt ?? "—"
                )
            }
        }
    }
}

private struct FlexWarningCard: View {
    let overview: MobileOverview

    var body: some View {
        EMSCard(title: "Flexibiliteit", systemImage: "exclamationmark.triangle.fill") {
            Text(overview.flex.status ?? "UNAVAILABLE")
                .font(.headline)
                .foregroundStyle(.orange)

            Text("Flex-beslissing wordt niet als actuele waarheid getoond.")
                .foregroundStyle(.secondary)

            if let age = overview.flex.ageSec {
                Text("Bronleeftijd: \(Int(age)) s")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct DeadlineScreen: View {
    @EnvironmentObject private var overviewStore: OverviewStore
    @EnvironmentObject private var deadlineStore: DeadlineStore

    let baseURL: String

    @State private var currentSocText = ""
    @State private var targetSocText = ""
    @State private var deadline = Date().addingTimeInterval(4 * 60 * 60)
    @State private var maxA = 11
    @State private var hasControlPIN = false
    @State private var localError: String?
    @State private var confirmSubmit = false
    @State private var confirmCancel = false

    private let amsterdamTimeZone = TimeZone(identifier: "Europe/Amsterdam")!

    var body: some View {
        Form {
            Section("Deadline-opdracht op Pi") {
                if deadlineStore.isLoading {
                    ProgressView()
                } else if let current = deadlineStore.current, current.active {
                    if overviewStore.overview?.ev.deadlineActive == true {
                        Label("Actief in EMS", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    } else {
                        Label("Opdracht geaccepteerd · uitvoering nog niet actief", systemImage: "clock")
                            .foregroundStyle(.secondary)
                    }
                    LabeledContent(
                        "SOC",
                        value: "\(current.currentSoc ?? 0)% → \(current.targetSoc ?? 0)%"
                    )
                    LabeledContent(
                        "Klaar om",
                        value: displayDeadline(current.deadline)
                    )
                    LabeledContent(
                        "Max",
                        value: current.maxA.map { "\($0) A" } ?? "—"
                    )

                    Button("Deadline annuleren", role: .destructive) {
                        confirmCancel = true
                    }
                    .disabled(deadlineStore.isSubmitting || !hasControlPIN)
                } else {
                    Text("Geen actieve deadline")
                        .foregroundStyle(.secondary)
                }
            }

            Section("Nieuwe deadline") {
                TextField("Huidige SOC (%)", text: $currentSocText)
                    .keyboardType(.numberPad)

                TextField("Doel SOC (%)", text: $targetSocText)
                    .keyboardType(.numberPad)

                DatePicker(
                    "Klaar om",
                    selection: $deadline,
                    in: Date().addingTimeInterval(61)...,
                    displayedComponents: [.date, .hourAndMinute]
                )
                .environment(\.timeZone, amsterdamTimeZone)

                Stepper(
                    "Max laadstroom: \(maxA) A",
                    value: $maxA,
                    in: 6...16
                )

                Text("Deadline wordt geïnterpreteerd als Nederlandse tijd.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section {
                Button {
                    confirmSubmit = true
                } label: {
                    if deadlineStore.isSubmitting {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("Deadline instellen")
                            .frame(maxWidth: .infinity)
                    }
                }
                .disabled(!canSubmit || deadlineStore.isSubmitting)
            } footer: {
                if !hasControlPIN {
                    Text("Sla eerst de Tesla control-PIN veilig op bij Instellingen.")
                }
            }

            if let message = deadlineStore.statusMessage {
                Section("Status") {
                    Text(message)
                }
            }

            if let error = localError ?? deadlineStore.errorMessage {
                Section("Fout") {
                    Text(error)
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Laaddeadline")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await refresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
        }
        .task {
            refreshPINState()
            await refresh()
        }
        .alert("Deadline instellen?", isPresented: $confirmSubmit) {
            Button("Annuleren", role: .cancel) {}
            Button("Bevestigen") {
                Task { await submit() }
            }
        } message: {
            Text(submitSummary)
        }
        .alert("Deadline annuleren?", isPresented: $confirmCancel) {
            Button("Behouden", role: .cancel) {}
            Button("Annuleren", role: .destructive) {
                Task { await cancel() }
            }
        } message: {
            Text("De actieve EV-laaddeadline wordt ingetrokken. De normale PV-opportunitylogica blijft daarna gelden.")
        }
    }

    private var parsedCurrentSoc: Int? {
        Int(currentSocText)
    }

    private var parsedTargetSoc: Int? {
        Int(targetSocText)
    }

    private var canSubmit: Bool {
        guard !baseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              hasControlPIN,
              let current = parsedCurrentSoc,
              let target = parsedTargetSoc
        else {
            return false
        }

        return (0...99).contains(current)
            && (1...100).contains(target)
            && target > current
            && (6...16).contains(maxA)
            && deadline.timeIntervalSinceNow > 60
    }

    private var submitSummary: String {
        guard let current = parsedCurrentSoc, let target = parsedTargetSoc else {
            return "Controleer de SOC-waarden."
        }
        return "Van \(current)% naar \(target)% · klaar \(displayDate(deadline)) · maximaal \(maxA) A. De Pi valideert de opdracht opnieuw."
    }

    private func refreshPINState() {
        do {
            hasControlPIN = try TeslaControlPINStore.load() != nil
            localError = nil
        } catch {
            hasControlPIN = false
            localError = error.localizedDescription
        }
    }

    private func refresh() async {
        await deadlineStore.loadCurrent(baseURLText: baseURL)
        if let current = deadlineStore.current, current.active {
            if let soc = current.currentSoc {
                currentSocText = String(soc)
            }
            if let target = current.targetSoc {
                targetSocText = String(target)
            }
            if let amps = current.maxA {
                maxA = amps
            }
            if let date = amsterdamDeadlineDate(current.deadline) {
                deadline = date
            }
        }
    }

    private func submit() async {
        localError = nil
        do {
            guard let pin = try TeslaControlPINStore.load() else {
                localError = "Tesla control-PIN ontbreekt."
                hasControlPIN = false
                return
            }
            guard let current = parsedCurrentSoc, let target = parsedTargetSoc else {
                localError = "Controleer de SOC-waarden."
                return
            }

            await deadlineStore.submit(
                currentSoc: current,
                targetSoc: target,
                deadline: deadline,
                maxA: maxA,
                baseURLText: baseURL,
                pin: pin
            )
            await overviewStore.refresh(baseURLText: baseURL)
        } catch {
            localError = error.localizedDescription
        }
    }

    private func cancel() async {
        localError = nil
        do {
            guard let pin = try TeslaControlPINStore.load() else {
                localError = "Tesla control-PIN ontbreekt."
                hasControlPIN = false
                return
            }

            await deadlineStore.cancel(baseURLText: baseURL, pin: pin)
            await overviewStore.refresh(baseURLText: baseURL)
        } catch {
            localError = error.localizedDescription
        }
    }

    private func displayDeadline(_ value: String?) -> String {
        guard let date = amsterdamDeadlineDate(value) else { return "—" }
        return displayDate(date)
    }

    private func displayDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "nl_NL")
        formatter.timeZone = amsterdamTimeZone
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

private struct SystemScreen: View {
    @EnvironmentObject private var store: OverviewStore

    var body: some View {
        List {
            if let overview = store.overview {
                Section("Flex") {
                    LabeledContent("Status", value: overview.flex.status ?? "—")
                    LabeledContent("Priority owner", value: overview.flex.priorityOwner ?? "—")
                    LabeledContent("EV role", value: overview.flex.evRole ?? "—")
                    LabeledContent(
                        "Consistent met EV deadline",
                        value: yesNo(overview.flex.consistentWithLiveEvDeadline)
                    )
                }

                Section("Manager") {
                    LabeledContent("Beslissing", value: overview.manager.decision ?? "—")
                    LabeledContent("Prioriteit", value: overview.manager.priority ?? "—")
                    if let reason = overview.manager.reason {
                        Text(reason)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Capabilities") {
                    LabeledContent("Read-only", value: overview.readOnly ? "Ja" : "Nee")
                    LabeledContent(
                        "Control writes",
                        value: overview.capabilities.controlWrites ? "Ja" : "Nee"
                    )
                    LabeledContent(
                        "Physical writes",
                        value: overview.capabilities.physicalWrites ? "Ja" : "Nee"
                    )
                }
            } else {
                ContentUnavailableView("Nog geen data", systemImage: "network")
            }
        }
        .navigationTitle("Systeemstatus")
    }
}

private struct SettingsScreen: View {
    @EnvironmentObject private var store: OverviewStore
    @Binding var baseURL: String

    @State private var newControlPIN = ""
    @State private var hasControlPIN = false
    @State private var pinMessage: String?

    var body: some View {
        Form {
            Section("EMS API") {
                TextField("Base URL", text: $baseURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                Button("Verbinding testen") {
                    Task { await store.refresh(baseURLText: baseURL) }
                }

                if let lastRefresh = store.lastRefresh {
                    LabeledContent(
                        "Laatste refresh",
                        value: lastRefresh.formatted(date: .omitted, time: .standard)
                    )
                }

                if let error = store.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }

            Section("Tesla deadline") {
                SecureField("Control-PIN", text: $newControlPIN)
                    .textContentType(.password)

                Button("PIN veilig opslaan") {
                    savePIN()
                }
                .disabled(newControlPIN.trimmingCharacters(in: .whitespacesAndNewlines).count < 8)

                if hasControlPIN {
                    Label("PIN opgeslagen in iOS Keychain", systemImage: "lock.fill")
                        .foregroundStyle(.secondary)

                    Button("PIN verwijderen", role: .destructive) {
                        deletePIN()
                    }
                }

                if let pinMessage {
                    Text(pinMessage)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Boundary") {
                Text("Dashboard en Mobile API V1 blijven read-only. v0.2 heeft één bounded write-pad: een EV-laaddeadline via de bestaande Tailscale/Pi command-ingang. Geen directe Homey- of device-writes.")
                    .font(.footnote)
            }
        }
        .navigationTitle("Instellingen")
        .onAppear {
            refreshPINState()
        }
    }

    private func refreshPINState() {
        do {
            hasControlPIN = try TeslaControlPINStore.load() != nil
        } catch {
            hasControlPIN = false
            pinMessage = error.localizedDescription
        }
    }

    private func savePIN() {
        do {
            try TeslaControlPINStore.save(newControlPIN)
            newControlPIN = ""
            hasControlPIN = true
            pinMessage = "Control-PIN veilig opgeslagen."
        } catch {
            pinMessage = error.localizedDescription
        }
    }

    private func deletePIN() {
        do {
            try TeslaControlPINStore.delete()
            newControlPIN = ""
            hasControlPIN = false
            pinMessage = "Control-PIN verwijderd."
        } catch {
            pinMessage = error.localizedDescription
        }
    }
}

private struct EMSCard<Content: View>: View {
    let title: String
    let systemImage: String
    let content: Content

    init(
        title: String,
        systemImage: String,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.systemImage = systemImage
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: systemImage)
                .font(.headline)
            content
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
    }
}

private struct Metric: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value)
                .font(.subheadline.bold())
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

private func effectiveHotWaterMode(_ overview: MobileOverview) -> String? {
    if let mode = overview.hotWater.mode, mode == "CV" || mode == "BOILER" {
        return mode
    }

    if let mode = overview.hotWater.seasonalAdvice?.data?.currentMode,
       mode == "CV" || mode == "BOILER" {
        return mode
    }

    return nil
}

private func localTime(_ value: String) -> String {
    let fractional = ISO8601DateFormatter()
    fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

    let standard = ISO8601DateFormatter()
    standard.formatOptions = [.withInternetDateTime]

    guard let date = fractional.date(from: value) ?? standard.date(from: value) else {
        return value
    }

    return date.formatted(date: .omitted, time: .shortened)
}

private func power(_ value: Double?) -> String {
    guard let value else { return "—" }
    return "\(Int(value.rounded())) W"
}

private func amps(_ value: Double?) -> String {
    guard let value else { return "—" }
    return "\(Int(value.rounded())) A"
}

private func yesNo(_ value: Bool?) -> String {
    guard let value else { return "—" }
    return value ? "Ja" : "Nee"
}
