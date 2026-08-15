"use client"

import { useEffect, useMemo, useState } from "react"

import { DEMO_EVENTS, DEMO_INITIAL_STATE } from "./demo-investigation.fixture"
import { replayPresentation } from "./demo-reducer"

export function useDemoPlayback() {
  const [step, setStepState] = useState(0)
  const [isPlaying, setIsPlaying] = useState(true)

  useEffect(() => {
    if (!isPlaying || step >= DEMO_EVENTS.length) return
    const timer = window.setTimeout(() => {
      setStepState((current) => Math.min(current + 1, DEMO_EVENTS.length))
    }, DEMO_EVENTS[step]?.holdMs ?? 1800)
    return () => window.clearTimeout(timer)
  }, [isPlaying, step])

  const state = useMemo(
    () => replayPresentation(DEMO_INITIAL_STATE, DEMO_EVENTS, step),
    [step],
  )

  const setStep = (value: number) => {
    setIsPlaying(false)
    setStepState(Math.max(0, Math.min(value, DEMO_EVENTS.length)))
  }

  const replay = () => {
    setStepState(0)
    setIsPlaying(true)
  }

  return {
    state,
    step,
    totalSteps: DEMO_EVENTS.length,
    isPlaying: isPlaying && step < DEMO_EVENTS.length,
    setIsPlaying,
    setStep,
    replay,
  }
}
