// Candidate for Core v0.11i — AEG laundry active-state semantics.
// Prepared outside Homey. NOT DEPLOYED.
//
// Problem in v0.11h:
//   active = connected && (running || activeCycle || timeToEnd > 0)
// This marks applianceState="Ready To Start" as active when AEG retains a stale
// positive measure_timeToEnd value. Day-history then rejects every such sample as
// known-appliance-active, which can leave Planner cleanBaseSamples at 0.

const normalise = value => String(value ?? '').trim().toUpperCase();

function deriveLaundryState({ connectionState, applianceState, cyclePhase, timeToEnd }) {
  const connection = String(connectionState ?? 'Unknown');
  const appliance = String(applianceState ?? 'Unknown');
  const cycle = String(cyclePhase ?? 'Unavailable');
  const remainingMinutes = Math.max(0, Number.isFinite(Number(timeToEnd)) ? Number(timeToEnd) : 0);

  const A = normalise(appliance);
  const C = normalise(cycle);
  const connected = !['DISCONNECTED', 'OFFLINE', 'UNAVAILABLE'].includes(normalise(connection));
  const running = A === 'RUNNING';
  const activeCycle = C !== '' && ![
    'UNAVAILABLE', 'UNKNOWN', 'NONE', 'IDLE', 'READY', 'READY TO START',
    'FINISHED', 'COMPLETE', 'COMPLETED', 'END', 'ENDED'
  ].includes(C);
  const remaining = remainingMinutes > 0;

  // Explicit direct appliance states outrank retained/stale time-to-end values.
  const explicitlyInactive = [
    'IDLE', 'OFF', 'INACTIVE', 'READY', 'READY TO START', 'STANDBY',
    'FINISHED', 'COMPLETE', 'COMPLETED', 'END', 'ENDED'
  ].includes(A);

  // timeToEnd remains a fallback only when the direct appliance state is not an
  // explicit inactive/ready state. RUNNING or an active cycle remain authoritative.
  const inferredFromRemaining = remaining && !explicitlyInactive && !running && !activeCycle;
  const active = connected && !explicitlyInactive && (running || activeCycle || inferredFromRemaining);

  const signals = [
    running ? 'APPLIANCE_RUNNING' : null,
    activeCycle ? 'ACTIVE_CYCLE' : null,
    inferredFromRemaining ? 'TIME_REMAINING' : null
  ].filter(Boolean);

  const conflict = connected && explicitlyInactive && (activeCycle || remaining);
  const source = running
    ? (activeCycle ? 'AEG_MULTI_SIGNAL' : 'APPLIANCE_RUNNING')
    : activeCycle
      ? 'ACTIVE_CYCLE'
      : inferredFromRemaining
        ? 'TIME_REMAINING'
        : conflict
          ? 'AEG_DIRECT_IDLE_OVERRIDES_RETAINED_SIGNAL'
          : 'AEG_DIRECT_IDLE';

  return {
    active,
    connectionState: connection,
    applianceState: appliance,
    cyclePhase: cycle,
    timeToEnd: remainingMinutes,
    source,
    inferred: !running && active,
    conflict
  };
}

// Regression cases. Throws when the candidate semantics regress.
const cases = [
  {
    name: 'Ready To Start overrides retained timeToEnd',
    input: { connectionState: 'Connected', applianceState: 'Ready To Start', cyclePhase: 'Unavailable', timeToEnd: 209 },
    expectedActive: false,
    expectedConflict: true
  },
  {
    name: 'Running is active',
    input: { connectionState: 'Connected', applianceState: 'Running', cyclePhase: 'Unavailable', timeToEnd: 42 },
    expectedActive: true
  },
  {
    name: 'Active cycle is active when appliance state is not explicitly idle',
    input: { connectionState: 'Connected', applianceState: 'Unknown', cyclePhase: 'Washing', timeToEnd: 35 },
    expectedActive: true
  },
  {
    name: 'timeToEnd may be fallback for unknown state',
    input: { connectionState: 'Connected', applianceState: 'Unknown', cyclePhase: 'Unavailable', timeToEnd: 35 },
    expectedActive: true
  },
  {
    name: 'Idle overrides retained timeToEnd',
    input: { connectionState: 'Connected', applianceState: 'Idle', cyclePhase: 'Unavailable', timeToEnd: 20 },
    expectedActive: false,
    expectedConflict: true
  },
  {
    name: 'Disconnected is inactive',
    input: { connectionState: 'Disconnected', applianceState: 'Running', cyclePhase: 'Washing', timeToEnd: 20 },
    expectedActive: false
  }
];

for (const test of cases) {
  const actual = deriveLaundryState(test.input);
  if (actual.active !== test.expectedActive) {
    throw new Error(`${test.name}: active=${actual.active}, expected ${test.expectedActive}`);
  }
  if ('expectedConflict' in test && actual.conflict !== test.expectedConflict) {
    throw new Error(`${test.name}: conflict=${actual.conflict}, expected ${test.expectedConflict}`);
  }
}

if (typeof module !== 'undefined') module.exports = { deriveLaundryState, cases };
