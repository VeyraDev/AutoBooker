import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import {
  confirmWritingBasis,
  getWritingBasis,
  patchWritingBasis,
  type WritingBasis,
} from "@/features/assistant/api/assistantApi";

export function useWritingBasis(bookId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["writingBasis", bookId],
    queryFn: () => getWritingBasis(bookId),
    enabled: Boolean(bookId && (options?.enabled ?? true)),
    retry: (count, err) => {
      if (axios.isAxiosError(err) && err.response?.status === 404) return false;
      return count < 1;
    },
  });
}

export function usePatchWritingBasis(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<WritingBasis>) => patchWritingBasis(bookId, patch),
    onSuccess: (data) => {
      qc.setQueryData(["writingBasis", bookId], data);
    },
  });
}

export function useConfirmWritingBasis(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => confirmWritingBasis(bookId),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["writingBasis", bookId] }),
        qc.invalidateQueries({ queryKey: ["intake", bookId] }),
      ]);
    },
  });
}
