import { payloadHash } from "./hash.js";
import type { Finding } from "./validate.js";
import type { OmCode } from "./codes.js";

/** Consistency tolerances (§H.4 [OM-ERR-002]) - configurable; mirrors the Python Tolerances. */
export interface Tolerances {
  capRateAbs: number; // absolute, cap rate is itself a small fraction
  monetaryRel: number; // relative, for money/PSF cross-checks
  rateAbs: number; // absolute, for escalation-rate checks
  capRateBand: [number, number]; // §H.4 tol.capRateBand (OMW-W013)
  remainingTermDays: number; // §H.4 tol.remainingTermDays (OMW-W030)
  leaseTermDays: number; // §H.4 tol.leaseTermDays (OMW-W031)
}

export const DEFAULT_TOLERANCES: Tolerances = {
  capRateAbs: 0.005,
  monetaryRel: 0.01,
  rateAbs: 0.005,
  capRateBand: [0.02, 0.2],
  remainingTermDays: 31,
  leaseTermDays: 31,
};

const DAYS_PER_MONTH = 30.4375; // 365.25 / 12, for month<->day term arithmetic

/** Optional context for the consistency tier - mirrors the Python `as_of` parameter. */
export interface ConsistencyOptions {
  /** Processing date (YYYY-MM-DD) for OMW-W032; without it, W032 is silent (no wall clock). */
  asOf?: string;
}

const NET_LEASE_TYPES = new Set(["NN", "NNN", "absolute-net"]);
const GROSS_LEASE_TYPES = new Set(["gross", "modified-gross"]);
const ALL_RESP = ["roof", "structure", "parking", "hvac", "taxes", "insurance", "cam"] as const;
const STRUCTURAL_RESP = ["roof", "structure", "parking", "hvac"] as const;

// Exported for the drift-lock (#151): tests assert this matches the canonical spec/codes.json registry.
export const REQUIREMENT: Record<string, string> = {
  "OMW-W010": "OM-CONS-010",
  "OMW-W011": "OM-CONS-011",
  "OMW-W012": "OM-CONS-012",
  "OMW-W013": "OM-CONS-013",
  "OMW-W014": "OM-CONS-014",
  "OMW-W020": "OM-CONS-020",
  "OMW-W021": "OM-CONS-021",
  "OMW-W022": "OM-CONS-022",
  "OMW-W023": "OM-CONS-023",
  "OMW-W024": "OM-CONS-024",
  "OMW-W025": "OM-CONS-025",
  "OMW-W026": "OM-CONS-026",
  "OMW-W030": "OM-CONS-030",
  "OMW-W031": "OM-CONS-031",
  "OMW-W032": "OM-CONS-032",
  "OMW-W033": "OM-CONS-033",
  "OMW-W034": "OM-CONS-034",
  "OMW-W040": "OM-CONS-040",
  "OMW-W041": "OM-CONS-041",
  "OMW-W050": "OM-CONS-050",
  "OMW-W060": "OM-CONS-060",
  "OMW-W061": "OM-DD-002",
  "OMI-I001": "OM-DD-002",
  "OMI-I002": "OM-DD-004",
  "OMI-I003": "OM-ERR-014",
};

function warn(
  code: OmCode,
  path: string,
  message: string,
  expected?: unknown,
  actual?: unknown,
): Finding {
  return {
    code,
    severity: "warning",
    path,
    message,
    requirement: REQUIREMENT[code]!,
    expected,
    actual,
  };
}

function infoFinding(code: OmCode, path: string, message: string): Finding {
  return { code, severity: "info", path, message, requirement: REQUIREMENT[code]! };
}

/** The value as an ISO date string when it already is one, else undefined (for expected/actual). */
function isoOf(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function relOff(actual: number, expected: number): number {
  return expected ? Math.abs(actual - expected) / Math.abs(expected) : Infinity;
}

/** Parse a strict YYYY-MM-DD date to a UTC epoch-day, or null. */
function epochDay(value: unknown): number | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const ms = Date.parse(`${value}T00:00:00Z`);
  return Number.isNaN(ms) ? null : Math.round(ms / 86_400_000);
}

function obj(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

/**
 * Consistency (warning) + info tier (§H) - mirror of the Python core's _warning_tier/_info_tier.
 * Internal-consistency only, never market truth; warnings/info NEVER block.
 */
export function consistencyFindings(
  payload: Record<string, unknown>,
  tol: Tolerances = DEFAULT_TOLERANCES,
  options: ConsistencyOptions = {},
): { warnings: Finding[]; info: Finding[] } {
  const warnings: Finding[] = [];
  const info: Finding[] = [];
  const deal = obj(payload.deal);
  const prop = obj(payload.property);
  const lease = obj(payload.lease);

  // Reference date for term checks (OMW-W030): explicit asOf, else the payload's assertedDate;
  // processingDate (OMW-W032) is set ONLY when a caller passes asOf - never the wall clock.
  const processingDate = options.asOf ? epochDay(options.asOf) : null;
  const asOfDate = processingDate !== null ? processingDate : epochDay(payload.assertedDate);
  dateTermChecks(lease, asOfDate, tol, warnings);
  dateSanityChecks(payload, deal, lease, processingDate, options.asOf, warnings);
  selfSupersedeCheck(payload, warnings);

  // OMW-W061 (#119): currency absent on an EXPLICITLY non-US property - the silent-USD default is
  // likely wrong. The plain absent case stays info (OMI-I001); this targets the real footgun.
  if (payload.currency === undefined || payload.currency === null) {
    const country = obj(prop.address).addressCountry;
    if (typeof country === "string" && country.toUpperCase() !== "US" && country !== "") {
      warnings.push(
        warn(
          "OMW-W061",
          "/currency",
          "currency absent on a non-US property; assumed USD - confirm the currency",
        ),
      );
    }
  }

  const cap = num(deal.capRate);
  const noi = num(deal.noi);
  const price = num(deal.askingPrice);
  const buildingSf = num(prop.buildingSF);

  if (cap !== null && noi !== null && price) {
    const implied = noi / price;
    if (Math.abs(cap - implied) > tol.capRateAbs) {
      warnings.push(
        warn(
          "OMW-W010",
          "/deal/capRate",
          "cap rate disagrees with NOI / askingPrice",
          round(implied, 4),
          cap,
        ),
      );
    }
  }
  const pps = num(deal.pricePerSF);
  if (pps !== null && price !== null && buildingSf) {
    const implied = price / buildingSf;
    if (relOff(pps, implied) > tol.monetaryRel) {
      warnings.push(
        warn(
          "OMW-W011",
          "/deal/pricePerSF",
          "price/SF disagrees with askingPrice / buildingSF",
          round(implied, 2),
          pps,
        ),
      );
    }
  }

  // OMW-W013: cap rate outside the plausibility band (§H.4 tol.capRateBand).
  if (cap !== null) {
    const [lo, hi] = tol.capRateBand;
    if (!(cap >= lo && cap <= hi)) {
      warnings.push(
        warn(
          "OMW-W013",
          "/deal/capRate",
          `capRate outside the plausibility band [${lo}, ${hi}]`,
          undefined,
          cap,
        ),
      );
    }
  }

  // OMW-W014: askingPrice, noi, or buildingSF is non-positive (§H.3).
  for (const [value, path, label] of [
    [price, "/deal/askingPrice", "askingPrice"],
    [noi, "/deal/noi", "noi"],
    [buildingSf, "/property/buildingSF", "buildingSF"],
  ] as const) {
    if (value !== null && value <= 0) {
      warnings.push(warn("OMW-W014", path, `${label} is non-positive`, undefined, value));
    }
  }

  // OMW-W012: pro-forma NOI presented without noiAsOfDate context.
  if (deal.noiType === "pro-forma" && !deal.noiAsOfDate) {
    warnings.push(
      warn("OMW-W012", "/deal/noiAsOfDate", "pro-forma NOI presented without noiAsOfDate context"),
    );
  }

  const leaseType = lease.leaseTypeAsserted;
  const resp = obj(lease.landlordResponsibilities);
  if (
    typeof leaseType === "string" &&
    NET_LEASE_TYPES.has(leaseType) &&
    (resp.taxes || resp.insurance || resp.cam)
  ) {
    warnings.push(
      warn(
        "OMW-W040",
        "/lease/landlordResponsibilities",
        `${leaseType} lease but landlord bears taxes/insurance/cam`,
      ),
    );
  }

  // OMW-W041: leaseTypeAsserted contradicts the responsibility set generally (§H.3).
  if (
    typeof leaseType === "string" &&
    GROSS_LEASE_TYPES.has(leaseType) &&
    Object.keys(resp).length > 0 &&
    !ALL_RESP.some((k) => resp[k])
  ) {
    warnings.push(
      warn(
        "OMW-W041",
        "/lease/landlordResponsibilities",
        `${leaseType} lease but landlord bears no responsibilities`,
      ),
    );
  } else if (leaseType === "absolute-net" && STRUCTURAL_RESP.some((k) => resp[k])) {
    warnings.push(
      warn(
        "OMW-W041",
        "/lease/landlordResponsibilities",
        "absolute-net lease but landlord bears structural/HVAC responsibilities",
      ),
    );
  }

  const schedule = Array.isArray(lease.rentSchedule) ? lease.rentSchedule : [];
  if (schedule.length > 0) {
    const firstRent = num(obj(schedule[0]).annualRent);
    if (firstRent !== null && noi !== null && deal.noiType === "in-place") {
      if (relOff(firstRent, noi) > tol.monetaryRel) {
        warnings.push(
          warn(
            "OMW-W020",
            "/lease/rentSchedule/0/annualRent",
            "year-1 annual rent disagrees with stated in-place NOI",
            noi,
            firstRent,
          ),
        );
      }
    }
    rentScheduleChecks(schedule, buildingSf, lease, tol, warnings);
  }

  infoTier(payload, deal, prop, lease, info);
  return { warnings, info };
}

/** OMW-W030/W031: stated term fields vs the date arithmetic (§H.4). */
function dateTermChecks(
  lease: Record<string, unknown>,
  asOfDate: number | null,
  tol: Tolerances,
  warnings: Finding[],
): void {
  const commencement = epochDay(lease.commencement);
  const expiration = epochDay(lease.expiration);
  const termMonths = num(lease.termMonths);
  const remainingMonths = num(lease.remainingTermMonths);

  if (termMonths !== null && commencement !== null && expiration !== null) {
    const actualDays = expiration - commencement;
    if (Math.abs(actualDays - termMonths * DAYS_PER_MONTH) > tol.leaseTermDays) {
      warnings.push(
        warn(
          "OMW-W031",
          "/lease/termMonths",
          "stated lease term disagrees with expiration - commencement",
          round(actualDays / DAYS_PER_MONTH, 1),
          termMonths,
        ),
      );
    }
  }
  if (remainingMonths !== null && expiration !== null && asOfDate !== null) {
    const actualDays = expiration - asOfDate;
    if (Math.abs(actualDays - remainingMonths * DAYS_PER_MONTH) > tol.remainingTermDays) {
      warnings.push(
        warn(
          "OMW-W030",
          "/lease/remainingTermMonths",
          "stated remaining term disagrees with expiration - as_of",
          round(actualDays / DAYS_PER_MONTH, 1),
          remainingMonths,
        ),
      );
    }
  }
}

/** OMW-W032/W033/W034: date-ordering sanity (§H.3). */
function dateSanityChecks(
  payload: Record<string, unknown>,
  deal: Record<string, unknown>,
  lease: Record<string, unknown>,
  processingDate: number | null,
  processingIso: string | undefined,
  warnings: Finding[],
): void {
  const asserted = epochDay(payload.assertedDate);
  const noiAsOf = epochDay(deal.noiAsOfDate);
  const commencement = epochDay(lease.commencement);
  const expiration = epochDay(lease.expiration);

  if (processingDate !== null && asserted !== null && asserted > processingDate) {
    warnings.push(
      warn(
        "OMW-W032",
        "/assertedDate",
        "assertedDate is in the future relative to the processing date",
        isoOf(processingIso),
        isoOf(payload.assertedDate),
      ),
    );
  }
  if (noiAsOf !== null && asserted !== null && noiAsOf > asserted) {
    warnings.push(
      warn(
        "OMW-W033",
        "/deal/noiAsOfDate",
        "noiAsOfDate is after assertedDate",
        isoOf(payload.assertedDate),
        isoOf(deal.noiAsOfDate),
      ),
    );
  }
  if (commencement !== null && expiration !== null && expiration <= commencement) {
    warnings.push(
      warn(
        "OMW-W034",
        "/lease/expiration",
        "lease expiration is on or before commencement",
        undefined,
        isoOf(lease.expiration),
      ),
    );
  }
}

/** OMW-W050: self-supersede - supersedes == hash of the payload with the pointer removed (§H.3). */
function selfSupersedeCheck(payload: Record<string, unknown>, warnings: Finding[]): void {
  const meta = obj(payload.meta);
  const supersedes = meta.supersedes;
  if (typeof supersedes !== "string") return;
  const strippedMeta = { ...meta };
  delete strippedMeta.supersedes;
  const stripped = { ...payload, meta: strippedMeta };
  let own: string;
  try {
    own = payloadHash(stripped);
  } catch {
    return; // hashing must never break validation
  }
  if (supersedes === own) {
    warnings.push(
      warn(
        "OMW-W050",
        "/meta/supersedes",
        "meta.supersedes equals this payload's own hash minus the pointer",
      ),
    );
  }
}

/** Info tier (§H.3): OMI-I001 (defaulted currency), I002 (source absent), I003 (skipped check). */
function infoTier(
  payload: Record<string, unknown>,
  deal: Record<string, unknown>,
  prop: Record<string, unknown>,
  lease: Record<string, unknown>,
  info: Finding[],
): void {
  const schedule = Array.isArray(lease.rentSchedule) ? lease.rentSchedule : [];
  const periods = schedule.map(obj);

  if (payload.currency === undefined) {
    info.push(
      infoFinding("OMI-I001", "/currency", "currency absent; assumed USD (OM-DD-002 default)"),
    );
  }
  if (periods.some((p) => p.source === undefined)) {
    info.push(
      infoFinding(
        "OMI-I002",
        "/lease/rentSchedule",
        "a rentPeriod source tag was absent; assumed 'asserted' (OM-DD-004)",
      ),
    );
  }
  const buildingSf = num(prop.buildingSF);
  if (num(deal.capRate) !== null && (num(deal.noi) === null || num(deal.askingPrice) === null)) {
    info.push(
      infoFinding(
        "OMI-I003",
        "/deal/capRate",
        "cap-rate cross-check (OMW-W010) skipped: noi or askingPrice absent",
      ),
    );
  }
  if (num(deal.pricePerSF) !== null && (num(deal.askingPrice) === null || buildingSf === null)) {
    info.push(
      infoFinding(
        "OMI-I003",
        "/deal/pricePerSF",
        "price/SF cross-check (OMW-W011) skipped: askingPrice or buildingSF absent",
      ),
    );
  }
  if (buildingSf === null && periods.some((p) => num(p.rentPSF) !== null)) {
    info.push(
      infoFinding(
        "OMI-I003",
        "/lease/rentSchedule",
        "rentPSF cross-check (OMW-W024) skipped: buildingSF absent",
      ),
    );
  }
}

function rentScheduleChecks(
  schedule: unknown[],
  buildingSf: number | null,
  lease: Record<string, unknown>,
  tol: Tolerances,
  warnings: Finding[],
): void {
  const commencement = epochDay(lease.commencement);
  const expiration = epochDay(lease.expiration);
  for (let i = 0; i < schedule.length; i++) {
    const period = obj(schedule[i]);
    const annual = num(period.annualRent);
    const rentPsf = num(period.rentPSF);
    const monthly = num(period.monthlyRent);
    const base = `/lease/rentSchedule/${i}`;

    if (rentPsf !== null && annual !== null && buildingSf) {
      const implied = annual / buildingSf;
      if (relOff(rentPsf, implied) > tol.monetaryRel) {
        warnings.push(
          warn(
            "OMW-W024",
            `${base}/rentPSF`,
            "rentPSF disagrees with annualRent / buildingSF",
            round(implied, 2),
            rentPsf,
          ),
        );
      }
    }
    if (monthly !== null && annual !== null) {
      if (relOff(monthly, annual / 12) > tol.monetaryRel) {
        warnings.push(
          warn(
            "OMW-W025",
            `${base}/monthlyRent`,
            "monthlyRent disagrees with annualRent / 12",
            round(annual / 12, 2),
            monthly,
          ),
        );
      }
    }
    if (period.source === "verified") {
      warnings.push(
        warn(
          "OMW-W060",
          `${base}/source`,
          "source is 'verified' but no corroborating verification metadata is present",
        ),
      );
    }
    const pStart = epochDay(period.periodStart);
    const pEnd = epochDay(period.periodEnd);
    if (commencement !== null && pStart !== null && pStart < commencement) {
      warnings.push(
        warn("OMW-W026", `${base}/periodStart`, "rent period starts before lease commencement"),
      );
    }
    if (expiration !== null && pEnd !== null && pEnd > expiration) {
      warnings.push(
        warn("OMW-W026", `${base}/periodEnd`, "rent period ends after lease expiration"),
      );
    }

    if (i === 0) continue;
    const prior = obj(schedule[i - 1]);
    const prevEnd = epochDay(prior.periodEnd);
    const esc = num(period.escalationFromPrior);
    const prevAnnual = num(prior.annualRent);
    if (esc !== null && prevAnnual && annual !== null) {
      const impliedStep = annual / prevAnnual - 1;
      if (Math.abs(esc - impliedStep) > tol.rateAbs) {
        warnings.push(
          warn(
            "OMW-W023",
            `${base}/escalationFromPrior`,
            "escalationFromPrior disagrees with the annualRent step",
            round(impliedStep, 4),
            esc,
          ),
        );
      }
    }
    if (prevEnd === null || pStart === null) continue;
    if (pStart <= prevEnd) {
      warnings.push(
        warn(
          "OMW-W022",
          `${base}/periodStart`,
          "rent-schedule period overlaps the previous period",
        ),
      );
    } else if (pStart - prevEnd > 1) {
      warnings.push(
        warn("OMW-W021", `${base}/periodStart`, "gap between consecutive rent-schedule periods"),
      );
    }
  }
}

function round(value: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}
