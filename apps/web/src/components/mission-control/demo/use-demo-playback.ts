"use client"

import { useEffect, useMemo, useState } from "react"

import type { DemoCaseDefinition } from "./demo-cases"
import { replayPresentation } from "./demo-reducer"

export function useDemoPlayback(demoCase: DemoCaseDefinition, enabled: boolean) {
  const [step, setStepState] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  useEffect(() => {
    if (!enabled || !isPlaying || step >= demoCase.events.length) return
    const timer = window.setTimeout(() => {
      setStepState((current) => Math.min(current + 1, demoCase.events.length))
    }, demoCase.events[step]?.holdMs ?? 1800)
    return () => window.clearTimeout(timer)
  }, [demoCase.events, enabled, isPlaying, step])

  const state = useMemo(
    () => replayPresentation(demoCase.initialState, demoCase.events, step),
    [demoCase, step],
  )

  const setStep = (value: number) => {
    setIsPlaying(false)
    setStepState(Math.max(0, Math.min(value, demoCase.events.length)))
  }

  const replay = () => {
    setStepState(0)
    setIsPlaying(true)
  }

  const start = () => {
    setStepState(0)
    setIsPlaying(true)
  }

  return {
    state,
    step,
    totalSteps: demoCase.events.length,
    isPlaying: enabled && isPlaying && step < demoCase.events.length,
    setIsPlaying,
    setStep,
    replay,
    start,
  }
}
