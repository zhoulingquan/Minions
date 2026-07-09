/**
 * Minions mascot (same as logo symbol). Used in Hero and Nav.
 */
import { CatPawIcon } from "./CatPawIcon";

interface MinionsMascotProps {
  size?: number;
  className?: string;
}

export function MinionsMascot({
  size = 80,
  className = "",
}: MinionsMascotProps) {
  return <CatPawIcon size={size} className={className} />;
}
