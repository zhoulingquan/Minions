import { useMemo } from "react";
import { getTimezoneOptions, type TimezoneOption } from "../constants/timezone";

export function useTimezoneOptions(): TimezoneOption[] {
    const language = "zh";
  return useMemo(() => {
    const locale = (language ?? "en").split("-")[0];
    return getTimezoneOptions(locale);
  }, [language]);
}
