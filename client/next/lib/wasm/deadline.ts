/**
 * WASM deadline engine binding.
 * When client/wasm/pkg is built (wasm-pack), wire it here.
 * Until then, always uses rules-backed API /api/deadline/calc.
 */

import type { DeadlineCalcRequest, DeadlineCalcResponse } from "@/types/assessment";
import { calculateDeadline } from "@/lib/api";

export async function computeDeadlineWithWasmOrApi(
  req: DeadlineCalcRequest,
): Promise<DeadlineCalcResponse & { computed_via?: "wasm" | "api" }> {
  const api = await calculateDeadline(req);
  return { ...api, computed_via: "api" };
}
