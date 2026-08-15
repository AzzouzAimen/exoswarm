import { LockClosedIcon } from "@heroicons/react/24/outline"

import type { InvestigationPresentationState } from "./model/presentation-state"

export function LockRevealPanel({ state }: { state: InvestigationPresentationState }) {
  if (!state.lock) return null

  return (
    <div className="lock-seal" role="status" aria-live="polite">
      <span className="lock-seal-icon" aria-hidden="true">
        <LockClosedIcon />
      </span>
      <span className="lock-seal-copy">
        <strong>Result saved</strong>
        <small>The catalog answer stays hidden</small>
      </span>
      <span className="lock-hash telemetry">
        SHA-256 · {state.lock.hash.slice(0, 8)}…{state.lock.hash.slice(-8)}
      </span>
    </div>
  )
}
