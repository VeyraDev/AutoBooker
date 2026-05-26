import { useQuery } from "@tanstack/react-query";

import { fetchLlmModels } from "@/api/config";

export function useLlmModels() {
  return useQuery({
    queryKey: ["llm-models"],
    queryFn: fetchLlmModels,
    staleTime: 5 * 60 * 1000,
  });
}
