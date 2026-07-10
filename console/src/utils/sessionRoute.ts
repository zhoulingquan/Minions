export type SessionRouteMode = "chat";

export function getSessionIdFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/chat\/(.+)$/);
  return match?.[1];
}

export function buildBasePath(mode: SessionRouteMode): string {
  return `/${mode}`;
}

export function buildSessionPath(
  mode: SessionRouteMode,
  sessionId?: string | null,
): string {
  const basePath = buildBasePath(mode);
  return sessionId ? `${basePath}/${sessionId}` : basePath;
}
