// EM v2 | 12 Input | Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER
// Canonical runtime source for the hourly FULL reconciliation action.
// SHADOW only. No device writes. No retries. Quooker deliberately excluded.

const SNAP = '05b27e13-9ebe-42af-8371-11c1f7148309';
const LEASE = '8891c3aa-d93a-47c3-a047-acd460cdc032';

const parse = x => {
  if (x == null || x === '') return null;
  if (typeof x !== 'string') return x;
  try { return JSON.parse(x); } catch { return x; }
};
const read = async id => (await Homey.logic.getVariable({ id })).value;

const INPUT = {
  ctxAt: '917704c9-8038-4914-9205-c552b4f1939a',
  pvTop: '0bb18a3a-0420-4e94-81ff-dc00b9215434',
  pNeg: '0c94479a-495a-40b4-9de9-dbd63092cecb',
  pCheap: '010392a1-7d56-4c70-be75-9b38cdec71be',
  pExp: 'e66c8f24-27fa-4bf9-8f57-f3eeaca80ca0',
  evActive: 'c35d4237-f173-4913-ae23-9434d6a98b70',
  evDeadline: '1173209b-2853-4fe2-b21b-507cea606ce6',
  evLatest: 'bf00e544-7ef1-4778-b8cd-4e0812198850',
  evKwh: '085eb4ed-80e8-4d37-92a0-56437f40b77f',
  evStatus: 'd0254ca9-5e4e-4cd5-8228-b1c25e6b9e3e',
  wwMode: 'f9d885a4-fca2-4aea-a5a9-a5c05da90835',
  wwPost: '1685e7b7-af04-4e0d-b4ed-78bef0d6bd42',
  priceCtx: '93e41221-6b4d-4f5f-83dc-997c9620f758',
  dayHist: '254f15cd-b060-4b42-801d-5e4f58efa069',
  contract: '211e5846-aada-4607-8d52-01b2ef578866',
  pbth: '29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b',
  lastPub: 'fc95dcad-55d5-4d21-be15-f565f0a9bac3',
  lastRev: 'c10ea01b-3dfc-4e04-bb27-2a56dfc636cd',
  lastVer: 'c8422ce3-093b-4781-ae20-67d2154c0a36'
};

const owner = `FULL:${Date.now()}:${Math.random()}`;
let lease = parse(await read(LEASE)) || {};
if (lease.owner && Date.parse(lease.expiresAt || 0) > Date.now()) return true;

await Homey.logic.updateVariable({
  id: LEASE,
  variable: {
    value: JSON.stringify({
      schema: 'EM2_CORE_INPUT_LEASE_V0.1',
      owner,
      expiresAt: new Date(Date.now() + 15000).toISOString()
    })
  }
});

lease = parse(await read(LEASE)) || {};
if (lease.owner !== owner) return true;

try {
  const keys = Object.keys(INPUT);
  const values = Object.fromEntries(
    await Promise.all(keys.map(async key => [key, await read(INPUT[key])]))
  );

  const current = await Homey.logic.getVariable({ id: SNAP });
  let snapshot = parse(current.value);
  if (!snapshot || typeof snapshot !== 'object') {
    snapshot = { schema: 'EM2_CORE_INPUT_V0.1', revision: 0, sources: {} };
  }

  const nextSources = {
    context: {
      updatedAt: values.ctxAt,
      pvTop4h: values.pvTop,
      priceNegative: values.pNeg,
      priceCheapNext4h: values.pCheap,
      priceExpensiveNext4h: values.pExp
    },
    teslaGoal: {
      deadlineActive: values.evActive,
      deadline: values.evDeadline,
      latestStart: values.evLatest,
      remainingKWh: values.evKwh,
      status: values.evStatus
    },
    hotWater: {
      boilerMode: values.wwMode,
      postGoalOpportunity: parse(values.wwPost)
    },
    planner: {
      contractPriceContext: parse(values.priceCtx),
      dayHistory: parse(values.dayHist),
      contractType: values.contract,
      priceBuffer: parse(values.pbth)
    },
    publication: {
      lastPublish: values.lastPub,
      lastPublishedRevision: values.lastRev,
      lastPublisherVersion: values.lastVer
    },
    legacy: { wwStateV13: null }
  };

  if (JSON.stringify(snapshot.sources) !== JSON.stringify(nextSources)) {
    snapshot.schema = 'EM2_CORE_INPUT_V0.1';
    snapshot.sources = nextSources;
    snapshot.revision = Number(snapshot.revision || 0) + 1;
    snapshot.generatedAt = new Date().toISOString();
    await Homey.logic.updateVariable({
      id: SNAP,
      variable: { value: JSON.stringify(snapshot) }
    });
  }
  return true;
} finally {
  const currentLease = parse(await read(LEASE)) || {};
  if (currentLease.owner === owner) {
    await Homey.logic.updateVariable({
      id: LEASE,
      variable: {
        value: JSON.stringify({
          schema: 'EM2_CORE_INPUT_LEASE_V0.1',
          owner: null,
          expiresAt: null
        })
      }
    });
  }
}
