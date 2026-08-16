import type { Finding } from "./validate.js";

/** Consistency tolerances (§H.4 [OM-ERR-002]) — configurable; mirrors the Python Tolerances. */
export interface Tolerances {
  capRateAbs: number; // absolute, cap rate is itself a small fraction
  monetaryRel: number; // relative, for money/PSF cross-checks
  rateAbs: number; // absolute, for escalation-rate checks
}

export const DEFAULT_TOLERANCES: Tolerances = {
  capRateAbs: 0.005,
  monetaryRel: 0.01,
  rateAbs: 0.005,
};

const NET_LEASE_TYPES = new Set(["NN", "NNN", "absolute-net"]);

const REQUIREMENT: Record<string, string> = {
  "OMW-W010": "OM-CONS-010",
  "OMW-W011": "OM-CONS-011",
  "OMW-W014": "OM-CONS-014",
  "OMW-W020": "OM-CONS-020",
  "OMW-W021": "OM-CONS-021",
  "OMW-W022": "OM-CONS-022",
  "OMW-W023": "OM-CONS-023",
  "OMW-W024": "OM-CONS-024",
  "OMW-W025": "OM-CONS-025",
  "OMW-W026": "OM-CONS-026",
  "OMW-W040": "OM-CONS-040",
  "OMI-I001": "OM-DD-030",
};

function warn(
  code: string,
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
 * Consistency (warning) + info tier (§H) — mirror of the Python core's _warning_tier/_info_tier.
 * Internal-consistency only, never market truth; warnings/info NEVER block.
 */
export function consistencyFindings(
  payload: Record<string, unknown>,
  tol: Tolerances = DEFAULT_TOLERANCES,
): { warnings: Finding[]; info: Finding[] } {
  const warnings: Finding[] = [];
  const info: Finding[] = [];
  const deal = obj(payload.deal);
  const prop = obj(payload.property);
  const lease = obj(payload.lease);

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

  if (deal.noiType === "pro-forma") {
    info.push({
      code: "OMI-I001",
      severity: "info",
      path: "/deal/noiType",
      message: "NOI is pro-forma (forward-looking), not in-place",
      requirement: REQUIREMENT["OMI-I001"]!,
    });
  }
  return { warnings, info };
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
    if (annual !== null && annual <= 0 && period.abatement === undefined) {
      warnings.push(
        warn(
          "OMW-W014",
          `${base}/annualRent`,
          "non-positive annualRent without an abatement",
          undefined,
          annual,
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
