import { useEffect, useMemo, useRef } from "react";

export function useDebouncedCallback(fn, delay = 600) {
  const fnRef = useRef(fn);
  const timerRef = useRef(null);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return useMemo(
    () =>
      (...args) => {
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => fnRef.current(...args), delay);
      },
    [delay]
  );
}
