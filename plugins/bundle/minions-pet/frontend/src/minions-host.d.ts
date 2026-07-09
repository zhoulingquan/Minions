// Ambient declarations for the Minions console host API.
//
// The Minions console injects a shared `window.Minions` object at
// runtime; we externalize `react`/`react-dom` (see `vite.config.ts`)
// and pull `React`/`antd` off `host` instead of bundling them. Without
// these declarations every access reduces to `any` and the compiler
// cannot tell us when the host contract drifts (e.g. `host.antd` being
// renamed or replaced).

import type * as ReactNS from "react";

declare global {
  interface MinionsHost {
    /** React module re-exported by the host (same major version as antd). */
    React: typeof ReactNS;
    /**
     * antd module re-exported by the host. Typed loosely on purpose:
     * antd's public types are huge and the plugin only uses a handful
     * of named exports through destructuring, so a structural `any`
     * shape here keeps the surface small while still letting `Pick`-
     * style destructuring compile.
     */
    antd: any;
    /** Resolve a console-relative API path to an absolute URL. */
    getApiUrl: (path: string) => string;
    /** Current bearer token for Minions API calls (may be empty). */
    getApiToken: () => string;
  }

  interface MinionsRoute {
    path: string;
    component: unknown;
    label?: string;
    icon?: string;
    priority?: number;
  }

  interface MinionsGlobal {
    host: MinionsHost;
    registerRoutes?: (pluginId: string, routes: MinionsRoute[]) => void;
  }

  interface Window {
    Minions: MinionsGlobal;
  }
}

export {};
