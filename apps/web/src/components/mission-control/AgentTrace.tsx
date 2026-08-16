"use client"

import { useEffect, useRef, useState, type ComponentType, type SVGProps } from "react"
import {
  ArrowRightIcon,
  BeakerIcon,
  CheckIcon,
  ChevronDownIcon,
  CircleStackIcon,
  ClockIcon,
  CpuChipIcon,
  DocumentCheckIcon,
  EyeIcon,
  GlobeAltIcon,
  LightBulbIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  MapIcon,
  ScaleIcon,
  ShieldCheckIcon,
  SignalIcon,
} from "@heroicons/react/24/outline"
import { RobotIcon } from "@sidekickicons/react/20/solid"
import { useReducedMotion } from "motion/react"

import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import ShinyText from "@/components/ui/ShinyText"
import { cn } from "@/lib/utils"

import { buildAgentTraceStages, type AgentTraceStage } from "./model/agent-trace"
import type {
  AgentId,
  InvestigationPresentationState,
  PresentationEventType,
  TimelineRecord,
} from "./model/presentation-state"
import { QuestionBot } from "./QuestionBot"

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>

const AGENT_ICONS: Record<AgentId, IconComponent> = {
  director: MapIcon,
  observer: EyeIcon,
  signal: SignalIcon,
  transit_hunter: GlobeAltIcon,
  skeptic: MagnifyingGlassIcon,
  critic: ShieldCheckIcon,
}

const AGENT_TASKS: Record<AgentId, string> = {
  director: "Decide whether the investigation can stop",
  observer: "Check the observation quality",
  signal: "Search for a repeating signal",
  transit_hunter: "Measure the candidate transit",
  skeptic: "Challenge the leading explanation",
  critic: "Review the proposed experiment",
}

const EVENT_ICONS: Record<PresentationEventType, IconComponent> = {
  "agent.started": LightBulbIcon,
  "agent.decision": ScaleIcon,
  "agent.handoff": ArrowRightIcon,
  "critic.review": ShieldCheckIcon,
  "tool.started": CpuChipIcon,
  "tool.completed": BeakerIcon,
  "evidence.appended": DocumentCheckIcon,
  "hypothesis.updated": CircleStackIcon,
  "result.locked": LockClosedIcon,
}

function activityLabel(stage: AgentTraceStage, state: InvestigationPresentationState) {
  if (stage.status !== "active") return "Complete"
  if (state.activeTool?.status === "running" && stage.records.at(-1)?.tool?.status === "running") {
    return "Running measurement"
  }
  if (stage.records.at(-1)?.eventType === "agent.handoff") return "Handing off"
  if (stage.agent.id === "critic" || stage.agent.status === "reviewing") return "Reviewing"
  return "Thinking"
}

function ActiveStatusText({ children }: { children: string }) {
  return (
    <span
      className="agent-trace-live-text"
      data-shiny-text-target="true"
      role="status"
      aria-live="polite"
    >
      {children}
    </span>
  )
}

function traceResult(record: TimelineRecord, state: InvestigationPresentationState) {
  if (record.evidenceRef) {
    const evidence = state.evidence.find((item) => item.id === record.evidenceRef)
    if (evidence) return evidence.summary
  }
  if (record.tool?.status === "complete" && record.tool.evidenceRef) {
    return `Returned ${record.tool.evidenceRef}`
  }
  return undefined
}

function TraceStep({
  record,
  state,
  currentStep,
  isActive,
  onSelect,
}: {
  record: TimelineRecord
  state: InvestigationPresentationState
  currentStep: number
  isActive: boolean
  onSelect: (step: number) => void
}) {
  const Icon = EVENT_ICONS[record.eventType]
  const result = traceResult(record, state)
  const isRunning = record.tool?.status === "running" && record.sequence === state.timeline.length
  const isCurrentWork = isActive && record.sequence === state.timeline.length

  return (
    <button
      type="button"
      className="agent-trace-step"
      data-tone={record.tone}
      data-current={record.sequence === currentStep}
      onClick={() => onSelect(record.sequence)}
      aria-label={`Go to step ${record.sequence}: ${record.headline}`}
    >
      <span className="agent-trace-step-icon" aria-hidden="true">
        <Icon />
      </span>
      <span className="agent-trace-step-copy">
        <span className="agent-trace-step-heading">
          <strong>
            {isCurrentWork ? (
              <ShinyText
                text={record.headline}
                color="var(--text-secondary)"
                shineColor="var(--science)"
                speed={1.4}
                delay={0.35}
              />
            ) : (
              record.headline
            )}
          </strong>
          {record.tool ? <code>{record.tool.name}</code> : null}
          <time className="telemetry">{record.timestamp}</time>
        </span>
        <span>{record.detail}</span>
        {result ? <small>{result}</small> : null}
      </span>
      {isRunning ? <ActiveStatusText>Running</ActiveStatusText> : null}
    </button>
  )
}

function AgentTraceStageView({
  stage,
  state,
  currentStep,
  onSelect,
}: {
  stage: AgentTraceStage
  state: InvestigationPresentationState
  currentStep: number
  onSelect: (step: number) => void
}) {
  const [open, setOpen] = useState(stage.status === "active")
  const stageRef = useRef<HTMLDivElement>(null)
  const shouldReduceMotion = useReducedMotion()
  const AgentIcon = AGENT_ICONS[stage.agent.id]
  const latestRecord = stage.records.at(-1)
  const statusLabel = activityLabel(stage, state)

  useEffect(() => {
    if (stage.status !== "active") return
    stageRef.current?.scrollIntoView({
      behavior: shouldReduceMotion ? "auto" : "smooth",
      block: "nearest",
    })
  }, [shouldReduceMotion, stage.status])

  return (
    <Collapsible
      ref={stageRef}
      className="agent-trace-stage"
      data-agent={stage.agent.id}
      data-status={stage.status}
      open={open}
      onOpenChange={setOpen}
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="agent-trace-stage-trigger"
          aria-label={`${open ? "Collapse" : "Expand"} ${stage.agent.label} activity`}
        >
          <span className="agent-trace-node" aria-hidden="true">
            {stage.status === "complete" ? <CheckIcon /> : <AgentIcon />}
          </span>
          <span className="agent-trace-stage-copy">
            <span className="agent-trace-stage-meta">
              <Badge variant="outline" className="agent-trace-agent-badge">
                <RobotIcon data-icon="inline-start" aria-hidden="true" />
                {stage.agent.label}
              </Badge>
              <span className="agent-trace-stage-function">{stage.agent.function}</span>
            </span>
            <span className="agent-trace-stage-title">
              {stage.status === "active" ? (
                <ShinyText
                  text={AGENT_TASKS[stage.agent.id]}
                  color="var(--text-primary)"
                  shineColor="var(--agent-color)"
                  speed={1.4}
                  delay={0.35}
                />
              ) : (
                AGENT_TASKS[stage.agent.id]
              )}
            </span>
            {latestRecord ? <small>{latestRecord.headline}</small> : null}
          </span>
          <span className={cn("agent-trace-stage-status", stage.status === "active" && "is-live")}>
            {stage.status === "active" ? (
              <ActiveStatusText>{statusLabel}</ActiveStatusText>
            ) : (
              statusLabel
            )}
          </span>
          <ChevronDownIcon className="agent-trace-chevron" aria-hidden="true" />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="agent-trace-stage-content">
        <div className="agent-trace-steps">
          {stage.records.map((record) => (
            <TraceStep
              key={record.id}
              record={record}
              state={state}
              currentStep={currentStep}
              isActive={stage.status === "active"}
              onSelect={onSelect}
            />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function AgentTrace({
  state,
  currentStep,
  onSelect,
}: {
  state: InvestigationPresentationState
  currentStep: number
  onSelect: (step: number) => void
}) {
  const stages = buildAgentTraceStages(state)
  const activeStage = stages.find((stage) => stage.status === "active")

  return (
    <section className="agent-trace" aria-labelledby="agent-trace-title">
      <header className="agent-trace-header">
        <div className="agent-trace-heading">
          <QuestionBot className="agent-trace-bot" />
          <div className="agent-trace-heading-copy">
            <span className="section-kicker">Investigation trace</span>
            <h1 id="agent-trace-title">
              {activeStage ? AGENT_TASKS[activeStage.agent.id] : state.phase === "locked" ? "Investigation complete" : "Agents ready"}
            </h1>
          </div>
        </div>
        <div className="agent-trace-count" aria-label={`${stages.length} agent stages recorded`}>
          <ClockIcon aria-hidden="true" />
          <span className="telemetry">{stages.length} stages · {state.timeline.length} steps</span>
        </div>
      </header>

      {stages.length ? (
        <ScrollArea className="agent-trace-scroll">
          <div className="agent-trace-list">
            {stages.map((stage) => (
              <AgentTraceStageView
                key={`${stage.id}-${stage.status}`}
                stage={stage}
                state={state}
                currentStep={currentStep}
                onSelect={onSelect}
              />
            ))}
          </div>
        </ScrollArea>
      ) : (
        <div className="agent-trace-empty">
          <span className="agent-trace-node" aria-hidden="true"><ClockIcon /></span>
          <div>
            <strong>Waiting for the first agent</strong>
            <span>The audit trail will appear as the investigation begins.</span>
          </div>
        </div>
      )}
    </section>
  )
}
