import { useEffect, useState } from "react";

/** The value once it has stopped changing for `ms`, so typing in a search box asks the engine once, not per letter. */
export function useDebouncedValue<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
