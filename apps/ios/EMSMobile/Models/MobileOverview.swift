import Foundation

struct MobileOverview: Decodable {
    let schema: String
    let generatedAt: String
    let readOnly: Bool
    let presentationOnly: Bool
    let energy: Energy
    let ev: EV
    let hotWater: HotWater
    let heating: Heating
    let flex: Flex
    let manager: Manager
    let capabilities: Capabilities

    struct Energy: Decodable {
        let gridPowerW: Double?
        let gridImportW: Double?
        let gridExportW: Double?
        let pvPowerW: Double?
        let otherHouseLoadW: Double?
        let stateAgeSec: Double?
        let gridMeasurementValid: Bool?
    }

    struct EV: Decodable {
        let connected: Bool?
        let charging: Bool?
        let powerW: Double?
        let requestedA: Double?
        let deadlineAt: String?
        let deadlineActive: Bool?
        let need: String?
        let remainingKWh: Double?
    }

    struct HotWater: Decodable {
        let mode: String?
        let boilerOn: Bool?
        let boilerPowerW: Double?
        let action: String?
        let seasonalAdvice: SeasonalAdvice?

        struct SeasonalAdvice: Decodable {
            let status: String?
            let data: Data?

            struct Data: Decodable {
                let generatedAt: String?
                let status: String?
                let advice: String?
                let currentMode: String?
                let confirmation: Confirmation?

                struct Confirmation: Decodable {
                    let confirmed: Bool?
                }
            }
        }
    }

    struct Heating: Decodable {
        let readyRooms: [String]
        let earliestOpportunityClosesAt: String?
        let shadowGrant: String?
    }

    struct Flex: Decodable {
        let status: String?
        let sourceGeneratedAt: String?
        let ageSec: Double?
        let consistentWithLiveEvDeadline: Bool?
        let priorityOwner: String?
        let evRole: String?
        let reason: String?
    }

    struct Manager: Decodable {
        let decision: String?
        let reason: String?
        let priority: String?
    }

    struct Capabilities: Decodable {
        let controlWrites: Bool
        let physicalWrites: Bool
    }
}
