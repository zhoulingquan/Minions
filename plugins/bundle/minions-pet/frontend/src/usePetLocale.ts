import type * as ReactNS from "react";
import { t, type MessageKey } from "./locale";

/** Pet UI locale — Chinese only. */
export function usePetLocale(React: typeof ReactNS) {
  const tr = React.useCallback(
    (key: MessageKey, params?: Record<string, string | number>) =>
      t(key, params),
    [],
  );

  return { locale: "zh" as const, tr };
}
