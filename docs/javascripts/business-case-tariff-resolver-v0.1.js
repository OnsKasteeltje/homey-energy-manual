export const BC_TARIFF_RESOLVER_SCHEMA = "EMS_BC_TARIFF_RESOLVER_V0.1";
const finite=v=>typeof v==="number"&&Number.isFinite(v);

/** Resolve the latest GOOD contract-history tariff at or before a sample timestamp.
 * No future tariff sample may be used. Explicit fallback is allowed but marked.
 */
export function createContractHistoryTariffResolver({contractHistory,maxAgeMinutes=30,fallback=null}={}){
  const rows=(Array.isArray(contractHistory)?contractHistory:contractHistory?.samples)||[];
  const normalized=rows.map(x=>({
    tsMs:Date.parse(String(x?.ts||x?.capturedAt||x?.price?.updatedAt||"")),
    contractType:String(x?.contractType||"").toUpperCase(),
    source:String(x?.price?.source||""),
    quality:String(x?.price?.quality||"").toUpperCase(),
    importPriceEuroPerKWh:Number(x?.price?.importNow),
    exportPriceEuroPerKWh:Number(x?.price?.exportNow)
  })).filter(x=>Number.isFinite(x.tsMs)&&x.quality==="GOOD"&&finite(x.importPriceEuroPerKWh)&&finite(x.exportPriceEuroPerKWh)).sort((a,b)=>a.tsMs-b.tsMs);
  const maxAgeMs=maxAgeMinutes*60_000;
  return sample=>{
    const t=Date.parse(String(sample?.ts||""));
    if(Number.isFinite(t)){
      let lo=0,hi=normalized.length-1,best=null;
      while(lo<=hi){const m=(lo+hi)>>1;if(normalized[m].tsMs<=t){best=normalized[m];lo=m+1;}else hi=m-1;}
      if(best&&t-best.tsMs<=maxAgeMs){return {schema:BC_TARIFF_RESOLVER_SCHEMA,importPriceEuroPerKWh:best.importPriceEuroPerKWh,exportPriceEuroPerKWh:best.exportPriceEuroPerKWh,contractType:best.contractType,tariffSource:"CONTRACT_HISTORY",source:best.source,quality:best.quality,tariffAt:new Date(best.tsMs).toISOString(),ageMinutes:(t-best.tsMs)/60_000};}
    }
    if(fallback&&finite(fallback.importPriceEuroPerKWh)&&finite(fallback.exportPriceEuroPerKWh))return {schema:BC_TARIFF_RESOLVER_SCHEMA,importPriceEuroPerKWh:fallback.importPriceEuroPerKWh,exportPriceEuroPerKWh:fallback.exportPriceEuroPerKWh,contractType:String(fallback.contractType||"UNKNOWN").toUpperCase(),tariffSource:"EXPLICIT_FALLBACK",source:fallback.source||"CONFIG",quality:"FALLBACK",tariffAt:null,ageMinutes:null};
    return {schema:BC_TARIFF_RESOLVER_SCHEMA,importPriceEuroPerKWh:null,exportPriceEuroPerKWh:null,contractType:null,tariffSource:"UNAVAILABLE",source:null,quality:"UNKNOWN",tariffAt:null,ageMinutes:null};
  };
}
