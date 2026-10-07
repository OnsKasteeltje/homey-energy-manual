import SwiftUI

struct ContentView: View {
    @StateObject private var store = OverviewStore()
    @AppStorage("emsBaseURL") private var baseURL = "http://192.168.1.42"

    var body: some View {
        TabView {
            NavigationStack {
                OverviewScreen(baseURL: baseURL)
            }
            .tabItem { Label("Overzicht", systemImage: "house.fill") }

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
        .task {
            await store.refresh(baseURLText: baseURL)
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
                    HotWaterCard(overview: overview)
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
                        description: Text(store.errorMessage ?? "Ververs om opnieuw te proberen.")
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
                Text(overview.generatedAt)
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
                    Text(overview.hotWater.mode ?? "Bron onbekend")
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
        EMSCard(title: "Verwarming", systemImage: "radiator") {
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

            Section("Boundary") {
                Text("v0.1 is uitsluitend read-only. De app bevat geen Homey-, planner- of device-writepad.")
                    .font(.footnote)
            }
        }
        .navigationTitle("Instellingen")
    }
}

private struct EMSCard<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder let content: Content

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
