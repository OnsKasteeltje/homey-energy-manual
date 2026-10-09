// Read-only UI guidance; never an EMS planner, telemetry source, or command writer.
// Must match the Pi's 0.62 kWh/SOC-% calibration for newly submitted commands.
export const KWH_PER_SOC_PERCENT=0.62;
const VOLTS=230;
const PHASES=3;
const DEFAULT_PREVIEW_AMPS=10;

// Returns an ideal minimum at continuous 3-phase charging; real charging may take longer.
export function estimateCharge(currentSoc,targetSoc,maxA){
  if(!Number.isInteger(currentSoc)||currentSoc<0||currentSoc>99||
     !Number.isInteger(targetSoc)||targetSoc<=currentSoc||targetSoc>100)return null;
  const kwh=Math.round((targetSoc-currentSoc)*KWH_PER_SOC_PERCENT*1000)/1000;
  if(kwh<1||kwh>75)return null; // Same command-domain bounds as the Pi.
  const assumedAmps=Number.isNaN(maxA)||maxA===null||maxA===undefined;
  const amps=assumedAmps?DEFAULT_PREVIEW_AMPS:maxA;
  if(!Number.isInteger(amps)||amps<6||amps>16)return null;
  const kw=PHASES*VOLTS*amps/1000;
  return {kwh,kw,amps,assumedAmps,minutes:Math.ceil(60*kwh/kw)};
}

export function formatDuration(minutes){
  const n=Math.ceil(minutes);
  if(!Number.isFinite(n)||n<0)return "—";
  if(n<60)return n+" min";
  const h=Math.floor(n/60),m=n%60;
  return h+" u"+(m?" "+m+" min":"");
}

// Interpret datetime-local explicitly in Europe/Amsterdam even when the
// browser runs in another timezone. Ambiguous or nonexistent DST clock times
// deliberately yield no feasibility verdict.
const AMSTERDAM=new Intl.DateTimeFormat("en-GB",{
  timeZone:"Europe/Amsterdam",year:"numeric",month:"2-digit",day:"2-digit",
  hour:"2-digit",minute:"2-digit",hourCycle:"h23"
});
export function availableMinutesInAmsterdam(deadline,nowMs){
  const m=/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)$/.exec(deadline||"");
  if(!m)return null;
  const [y,mo,d,h,mi]=m.slice(1).map(Number);
  const clock=Date.UTC(y,mo-1,d,h,mi);
  const matches=[];
  // Amsterdam's offset is UTC+01:00 or UTC+02:00.
  for(const hours of [1,2]){
    const epoch=clock-hours*3600000;
    const parts=Object.fromEntries(AMSTERDAM.formatToParts(new Date(epoch))
      .filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));
    if(Number(parts.year)===y&&Number(parts.month)===mo&&
       Number(parts.day)===d&&Number(parts.hour)===h&&
       Number(parts.minute)===mi)matches.push(epoch);
  }
  return matches.length===1?(matches[0]-nowMs)/60000:null;
}

export function deadlineFeedback(estimate,deadline,nowMs=Date.now()){
  if(!estimate||!deadline)return {level:"none",text:""};
  const available=availableMinutesInAmsterdam(deadline,nowMs);
  if(available===null)return {level:"info",text:"Deadline-tijd onduidelijk (mogelijk zomer-/wintertijd); Pi valideert bij opslaan."};
  if(available<=0)return {level:"warning",text:"Deadline verstreken. Kies een later tijdstip."};
  const availableRounded=Math.max(0,Math.floor(available));
  if(available<estimate.minutes)return {
    level:"warning",text:"Deadline te krap: "+formatDuration(availableRounded)+" beschikbaar, "+
      formatDuration(estimate.minutes)+" theoretisch nodig."
  };
  return {level:"info",text:"Tot deadline: "+formatDuration(availableRounded)+
    " beschikbaar. Theoretisch voldoende, zonder laadverliezen of reserve."};
}
