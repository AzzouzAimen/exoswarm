"use client"

import { AnimatePresence, motion, useReducedMotion } from "motion/react"

const BOUNDARIES = [
  { label: "Agent proposes", detail: "one allowed action", tone: "model" },
  { label: "Rules check it", detail: "schema and budget", tone: "model" },
  { label: "Code decides", detail: "permission boundary", tone: "science" },
  { label: "Tool measures", detail: "numbers come from code", tone: "science" },
  { label: "Evidence is saved", detail: "source attached", tone: "neutral" },
  { label: "Result is locked", detail: "catalog stays hidden", tone: "unresolved" },
] as const

export function XRayOverlay({
  visible,
  budget,
}: {
  visible: boolean
  budget: { used: number; total: number }
}) {
  const shouldReduceMotion = useReducedMotion()
  return (
    <AnimatePresence>
      {visible ? (
        <motion.aside
          className="xray-overlay"
          aria-label="System authority boundaries"
          initial={shouldReduceMotion ? false : { opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.985 }}
          transition={{ duration: shouldReduceMotion ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="xray-heading">
            <span>X-RAY · {budget.used}/{budget.total} test units used</span>
            <strong>Agents choose what to test. Code measures it.</strong>
          </div>
          <ol>
            {BOUNDARIES.map((boundary, index) => (
              <li key={boundary.label} data-tone={boundary.tone}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{boundary.label}</strong>
                <small>{boundary.detail}</small>
              </li>
            ))}
          </ol>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  )
}
