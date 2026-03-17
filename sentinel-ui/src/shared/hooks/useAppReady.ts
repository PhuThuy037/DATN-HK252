import { useMemo } from "react";

export function useAppReady() {
  return useMemo(() => true, []);
}
