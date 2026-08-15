"use client"

import { type ComponentType, type SVGProps } from "react"
import {
  CpuChipIcon,
  EyeIcon,
  GlobeAltIcon,
  MagnifyingGlassIcon,
  MapIcon,
  ShieldCheckIcon,
  SignalIcon,
} from "@heroicons/react/24/outline"

import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"

import type {
  AgentId,
  AgentPresentation,
  InvestigationPresentationState,
} from "./model/presentation-state"

const AGENT_ICONS: Record<AgentId, ComponentType<SVGProps<SVGSVGElement>>> = {
  director: MapIcon,
  observer: EyeIcon,
  signal: SignalIcon,
  transit_hunter: GlobeAltIcon,
  skeptic: MagnifyingGlassIcon,
  critic: ShieldCheckIcon,
}

function AgentInspector({ agent }: { agent: AgentPresentation }) {
  const detail = agent.inspector
  return (
    <PopoverContent className="agent-inspector" sideOffset={10} align="center">
      <PopoverHeader>
        <PopoverTitle>{agent.label.toUpperCase()}</PopoverTitle>
        <PopoverDescription>{agent.function}</PopoverDescription>
      </PopoverHeader>
      <dl className="inspector-grid">
        <div>
          <dt>Status</dt>
          <dd>{agent.status}</dd>
        </div>
        <div className="inspector-wide">
          <dt>Current question</dt>
          <dd>{detail.currentQuestion}</dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{detail.evidenceRefs.join(" · ") || "none"}</dd>
        </div>
        <div>
          <dt>Action</dt>
          <dd className="telemetry">{detail.action}</dd>
        </div>
        <div className="inspector-wide">
          <dt>Expected discriminator</dt>
          <dd>{detail.expectedDiscriminator}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{detail.model}</dd>
        </div>
        <div>
          <dt>Latency</dt>
          <dd>{detail.latency}</dd>
        </div>
        <div>
          <dt>Schema</dt>
          <dd data-schema={detail.schema}>{detail.schema}</dd>
        </div>
      </dl>
    </PopoverContent>
  )
}

function AgentNode({
  agent,
}: {
  agent: AgentPresentation
}) {
  const Icon = AGENT_ICONS[agent.id]
  const isWorking = agent.status === "active" || agent.status === "reviewing"

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="agent-node"
          data-agent={agent.id}
          data-status={agent.status}
          aria-label={`${agent.label} agent, ${agent.status}. ${agent.summary}`}
        >
          <span className="agent-icon" aria-hidden="true">
            <Icon />
          </span>
          <span className="agent-copy">
            <strong>{agent.label}</strong>
            {isWorking ? <small>Working</small> : null}
          </span>
        </button>
      </PopoverTrigger>
      <AgentInspector agent={agent} />
    </Popover>
  )
}

function ScienceToolNode({
  state,
}: {
  state: InvestigationPresentationState
}) {
  const tool = state.activeTool
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="science-tool-node"
          data-status={tool?.status ?? "idle"}
          aria-label={`Deterministic science tool. ${tool?.name ?? "No tool active"}.`}
        >
          <span className="tool-glyph" aria-hidden="true">
            <CpuChipIcon />
          </span>
          <span>
            <strong>Measurement</strong>
            {tool ? <small>{tool.status === "running" ? "Running" : "Done"}</small> : null}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="agent-inspector" side="top" sideOffset={10}>
        <PopoverHeader>
          <PopoverTitle>MEASUREMENT DETAILS</PopoverTitle>
          <PopoverDescription>Code—not an agent—produces every number.</PopoverDescription>
        </PopoverHeader>
        <dl className="inspector-grid">
          <div>
            <dt>Tool</dt>
            <dd className="telemetry">{tool?.name ?? "idle"}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{tool?.status ?? "idle"}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{tool?.durationMs ? `${tool.durationMs} ms` : "not complete"}</dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>{tool?.evidenceRef ?? "pending"}</dd>
          </div>
        </dl>
      </PopoverContent>
    </Popover>
  )
}

export function AgentActivity({ state }: { state: InvestigationPresentationState }) {
  return (
    <div className="agent-bar" aria-label="Investigation agents">
      <div className="agent-bar-label">
        <span>Team</span>
        <small>{state.activeAgentId ? "Agent working" : state.activeTool?.status === "running" ? "Measuring" : "Ready"}</small>
      </div>
      <div className="agent-list">
        {state.agents.map((agent) => (
          <AgentNode key={agent.id} agent={agent} />
        ))}
      </div>
      <ScienceToolNode state={state} />
    </div>
  )
}
