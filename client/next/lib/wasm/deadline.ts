/**
 * WASM deadline engine binding.
 * Loads client/wasm pkg when built; falls back to API /api/deadline/calc.
 */

import type { DeadlineCalcRequest, DeadlineCalcResponse } from "@/types/assessment";
import { calculateDeadline } from "@/lib/api";

type WasmDeadlineModule = {
  compute_deadline: (
    edt: string,
    months: number,
    ecA?: string,
    ecB?: string,
  ) => string;
};

let wasmModule: WasmDeadlineModule | null = null;
let wasmLoadAttempted = false;

async function loadWasm(): Promise<WasmDeadlineModule | null> {
  if (wasmLoadAttempted) return wasmModule;
  wasmLoadAttempted = true;
  try {
    // Built output from: cd client/wasm && wasm-pack build --target web
    const mod = await import(
      /* webpackIgnore: true */ "../../../wasm/pkg/lawapp_wasm.js"
    );
    if (mod?.default) await mod.default();
    wasmModule = mod as WasmDeadlineModule;
    return wasmModule;
  } catch {
    return null;
  }
}

export async function computeDeadlineWithWasmOrApi(
  req: DeadlineCalcRequest,
): Promise<DeadlineCalcResponse & { computed_via?: "wasm" | "api" }> {
  const wasm = await loadWasm();
  if (wasm?.compute_deadline) {
    try {
      const raw = wasm.compute_deadline(
        req.edt,
        3,
        req.ec_day_a || req.acas_start,
        req.ec_day_b || req.acas_end,
      );
      const parsed = JSON.parse(raw);
      if (!parsed.error) {
        return {
          limitation_date: parsed.limitation_date,
          base_deadline: parsed.base_limit,
          ec_applied: parsed.ec_applied,
          authority: parsed.authority,
          computed_via: "wasm",
        };
      }
    } catch {
      // fall through to API
    }
  }
  const api = await calculateDeadline(req);
  return { ...api, computed_via: "api" };
}
