export const BC_HISTORY_ADAPTER_SCHEMA="EMS_BC_HISTORY_ADAPTER_V0.1";
const finite=v=>typeof v==="number"&&Number.isFinite(v);

/**
 * Converts energy-day-v2 / day-series samples into BC replay samples.
 * Tariffs are supplied explicitly through either a resolver or fixed prices.
 * Unknown meter/tariff data stays unknown and will be rejected by the engine.
 */
export function adaptEnergyHistory({history,priceResolver=null,fixedImportPriceEuroPerKWh=null,fixedExportPriceEuroPerKWh=null}){
  const source=Array.isArray(history)?history:history?.samples;
  if(!Array.isArray(source))throw new Error("BC_HISTORY_SAMPLES_REQUIRED");
  const defaultInterval=finite(history?.sample_interval_minutes)?history.sample_interval_minutes:5;
  const samples=source.map((x,index)=>{
    let tariff={};
    if(typeof priceResolver==="function")tariff=priceResolver(x,index)||{};
    const importPrice=finite(tariff.importPriceEuroPerKWh)?tariff.importPriceEuroPerKWh:fixedImportPriceEuroPerKWh;
    const exportPrice=finite(tariff.exportPriceEuroPerKWh)?tariff.exportPriceEuroPerKWh:fixedExportPriceEuroPerKWh;
    return {
      ts:x?.ts??null,
      intervalMinutes:defaultInterval,
      gridW:finite(x?.p1W)?x.p1W:null,
      measurementValid:x?.p1Valid===true,
      importPriceEuroPerKWh:finite(importPrice)?importPrice:null,
      exportPriceEuroPerKWh:finite(exportPrice)?exportPrice:null,
      emsBatteryTargetW:finite(x?.batteryTargetW)?x.batteryTargetW:finite(x?.emsBatteryTargetW)?x.emsBatteryTargetW:null,
      evidence:{revision:x?.revision??null,held:x?.held===true,p1Source:x?.p1Source??null,teslaW:finite(x?.teslaW)?x.teslaW:null,boilerW:finite(x?.boilerW)?x.boilerW:null,pvW:[x?.solarEdgeW,x?.goodWe4200W,x?.goodWe2000W].filter(finite).reduce((a,b)=>a+b,0)}
    };
  });
  return {schema:BC_HISTORY_ADAPTER_SCHEMA,sourceSchema:history?.schema_version??null,dateLocal:history?.date_local??null,sampleIntervalMinutes:defaultInterval,samples};
}
