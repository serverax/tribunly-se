"use client";

import { useQuery } from "@tanstack/react-query";
import { getCase, listCases } from "@/lib/api";

export function useCases() {
  return useQuery({
    queryKey: ["cases"],
    queryFn: listCases,
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId!),
    enabled: Boolean(caseId),
  });
}
