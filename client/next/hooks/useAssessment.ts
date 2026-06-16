"use client";

import { useMutation } from "@tanstack/react-query";
import { runDiagnosis, runClaimAssessment, calculateDeadline } from "@/lib/api";
import { computeDeadlineWithWasmOrApi } from "@/lib/wasm/deadline";
import type { DeadlineCalcRequest, DiagnosisRequest } from "@/types/assessment";

export function useDiagnosis() {
  return useMutation({
    mutationFn: (body: DiagnosisRequest) => runDiagnosis(body),
  });
}

export function useClaimAssessment() {
  return useMutation({
    mutationFn: ({
      facts,
      matterId,
    }: {
      facts: string | Record<string, unknown>;
      matterId?: string;
    }) => runClaimAssessment(facts, matterId),
  });
}

export function useDeadlineCalc() {
  return useMutation({
    mutationFn: (body: DeadlineCalcRequest) => calculateDeadline(body),
  });
}

export function useDeadlineWasmOrApi() {
  return useMutation({
    mutationFn: (body: DeadlineCalcRequest) => computeDeadlineWithWasmOrApi(body),
  });
}
