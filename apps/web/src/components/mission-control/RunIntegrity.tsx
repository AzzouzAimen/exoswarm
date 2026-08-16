import { CpuChipIcon, ShieldCheckIcon } from "@heroicons/react/24/outline"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import type { RunIntegrityView } from "./view-models"

export function RunIntegrity({ result }: { result: RunIntegrityView }) {
  return (
    <aside className="run-integrity" aria-label="Run boundaries">
      <span>
        <CpuChipIcon aria-hidden="true" />
        <strong>{result.agentCalls}</strong> model calls
      </span>
      <span>
        <strong>{result.toolCalls}</strong> code checks
      </span>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="run-integrity-rule" tabIndex={0}>
            <ShieldCheckIcon aria-hidden="true" /> Agents choose checks; code measures
          </span>
        </TooltipTrigger>
        <TooltipContent>{result.provider && result.provider !== "not_measured" ? `${result.provider} · ${result.modelIdentity}` : "Agents see compact evidence summaries. Deterministic tools calculate the numeric results."}</TooltipContent>
      </Tooltip>
    </aside>
  )
}
