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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { buildAgentTraceStages, type AgentTraceStage } from "./model/agent-trace"
import type {
  AgentId,
  InvestigationPresentationState,
  PresentationEventType,
  TimelineRecord,
} from "./model/presentation-state"
import {
  clearTraceRevealTimer,
  createTraceRevealQueue,
  reconcileTraceRevealQueue,
  revealAllTraceRecords,
  revealNextTraceRecord,
  TRACE_REVEAL_INTERVAL_MS,
} from "./model/trace-pacing"
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
  director: "Route the next bounded check",
  observer: "Check the observation quality",
  signal: "Search for a repeating signal",
  transit_hunter: "Measure the candidate transit",
  skeptic: "Challenge the leading explanation",
  critic: "Review the proposed experiment",
}

const EVENT_ICONS: Record<PresentationEventType, IconComponent> = {
  "audit.event": ClockIcon,
  "agent.started": LightBulbIcon,
  "agent.decision": ScaleIcon,
  "agent.handoff": ArrowRightIcon,
  "critic.review": ShieldCheckIcon,
  "tool.started": CpuChipIcon,
  "tool.completed": BeakerIcon,
  "evidence.appended": DocumentCheckIcon,
  "hypothesis.updated": CircleStackIcon,
  "run.concluded": LockClosedIcon,
  "result.locked": LockClosedIcon,
}

const TOOL_LABELS: Record<string, string> = {
  search_bls: "Repeat-pattern search",
  odd_even: "Alternating-event check",
  secondary_eclipse: "Second-event check",
  contamination_screening: "Nearby-source risk check",
  harmonic_test: "Half / double timing check",
  alternate_detrend: "Reprocessing check",
}

const TOOL_HELP: Record<string, string> = {
  search_bls: "Deterministic code scans many possible repeat intervals. Backend name: search_bls.",
  odd_even: "Deterministic code compares alternating event depths. Backend name: odd_even.",
  secondary_eclipse: "Deterministic code searches for a second dimming event. Backend name: secondary_eclipse.",
  contamination_screening: "Code checks whether nearby sources could explain the signal. Backend name: contamination_screening.",
  harmonic_test: "Deterministic code compares the chosen timing with half and double periods. Backend name: harmonic_test.",
  alternate_detrend: "Code reprocesses the observation to test whether the signal survives. Backend name: alternate_detrend.",
}

const BOUNDARY_LABELS: Record<TimelineRecord["boundary"], string> = {
  agent: "Agent decision",
  review: "Independent review",
  code: "Code measurement",
  evidence: "Evidence saved",
  authority: "Result commitment",
}

function useProgressiveTimeline(state: InvestigationPresentationState) {
  const shouldReduceMotion = useReducedMotion()
  const initialQueue = createTraceRevealQueue(state.timeline, Boolean(shouldReduceMotion))
  const queueRef = useRef(initialQueue)
  const runIdRef = useRef(state.run.id)
  const timerRef = useRef<number | undefined>(undefined)
  const [renderedQueue, setRenderedQueue] = useState({
    visible: initialQueue.visible,
    pendingCount: initialQueue.pending.length,
  })

  useEffect(() => {
    const runChanged = runIdRef.current !== state.run.id
    runIdRef.current = state.run.id

    if (timerRef.current !== undefined && (runChanged || shouldReduceMotion)) {
      timerRef.current = clearTraceRevealTimer(timerRef.current, window.clearInterval)
    }

    let nextQueue = runChanged
      ? createTraceRevealQueue(state.timeline, Boolean(shouldReduceMotion))
      : reconcileTraceRevealQueue(queueRef.current, state.timeline)
    if (shouldReduceMotion) nextQueue = revealAllTraceRecords(nextQueue)
    queueRef.current = nextQueue
    setRenderedQueue({
      visible: nextQueue.visible,
      pendingCount: nextQueue.pending.length,
    })

    if (!nextQueue.pending.length || timerRef.current !== undefined) return

    timerRef.current = window.setInterval(() => {
      const advancedQueue = revealNextTraceRecord(queueRef.current)
      if (advancedQueue === queueRef.current) {
        timerRef.current = clearTraceRevealTimer(timerRef.current, window.clearInterval)
        return
      }

      queueRef.current = advancedQueue
      setRenderedQueue({
        visible: advancedQueue.visible,
        pendingCount: advancedQueue.pending.length,
      })

      if (!advancedQueue.pending.length) {
        timerRef.current = clearTraceRevealTimer(timerRef.current, window.clearInterval)
      }
    }, TRACE_REVEAL_INTERVAL_MS)
  }, [shouldReduceMotion, state.run.id, state.timeline])

  useEffect(() => () => {
    timerRef.current = clearTraceRevealTimer(timerRef.current, window.clearInterval)
  }, [])

  return renderedQueue
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
  const toolLabel = record.tool ? (TOOL_LABELS[record.tool.name] ?? record.tool.name) : undefined
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
          <span className="agent-trace-boundary" data-boundary={record.boundary}>
            {BOUNDARY_LABELS[record.boundary]}
          </span>
          {record.tool ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <code tabIndex={0}>{toolLabel}</code>
              </TooltipTrigger>
              <TooltipContent>{TOOL_HELP[record.tool.name] ?? `Deterministic backend tool: ${record.tool.name}`}</TooltipContent>
            </Tooltip>
          ) : null}
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
  const { visible: visibleTimeline, pendingCount } = useProgressiveTimeline(state)
  const traceState = { ...state, timeline: visibleTimeline }
  const groupedStages = buildAgentTraceStages(traceState)
  const stages = pendingCount && groupedStages.length
    ? groupedStages.map((stage, index) => ({
        ...stage,
        status: index === groupedStages.length - 1 ? "active" as const : "complete" as const,
      }))
    : groupedStages
  const activeStage = stages.find((stage) => stage.status === "active")

  return (
    <section className="agent-trace" aria-labelledby="agent-trace-title">
      <header className="agent-trace-header">
        <div className="agent-trace-heading">
          <QuestionBot className="agent-trace-bot" />
          <div className="agent-trace-heading-copy">
            <span className="section-kicker">Investigation trace</span>
            <h1 id="agent-trace-title">
              {activeStage ? (
                AGENT_TASKS[activeStage.agent.id]
              ) : state.phase === "locked" ? (
                "Investigation complete"
              ) : (
                <ShinyText
                  text="Agents working in process"
                  color="var(--text-primary)"
                  shineColor="var(--science)"
                  speed={1.4}
                  delay={0.35}
                />
              )}
            </h1>
          </div>
        </div>
        <div className="agent-trace-count" aria-label={`${stages.length} agent stages recorded`}>
          <ClockIcon aria-hidden="true" />
          <span className="telemetry">{stages.length} stages · {visibleTimeline.length} steps</span>
        </div>
      </header>

      {stages.length ? (
        <ScrollArea className="agent-trace-scroll">
          <div className="agent-trace-list">
            {stages.map((stage) => (
              <AgentTraceStageView
                key={stage.id}
                stage={stage}
                state={traceState}
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
