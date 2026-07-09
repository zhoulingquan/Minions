import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

export type Lang = "zh";

export const SiteLanguageContext = createContext<Lang>("zh");

export function SiteLanguageProvider({ children }: { children: ReactNode }) {
  return (
    <SiteLanguageContext.Provider value="zh">
      {children}
    </SiteLanguageContext.Provider>
  );
}

export function useSiteLanguage(): Lang {
  return useContext(SiteLanguageContext);
}
