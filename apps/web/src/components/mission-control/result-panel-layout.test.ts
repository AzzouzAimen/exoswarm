import { readFileSync } from "node:fs"

import { describe, expect, it } from "vitest"

const css = readFileSync(new URL("../../../app/globals.css", import.meta.url), "utf8")
const component = readFileSync(new URL("./ResultComparisonPanel.tsx", import.meta.url), "utf8")

const ruleFor = (selector: string) => {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  return css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]+)\\}`))?.[1] ?? ""
}

describe("result panel layout", () => {
  it("places the restart and review actions before the result heading", () => {
    const topActionsStart = component.indexOf('className="result-top-actions"')
    const headingStart = component.indexOf('className="result-panel-heading"')
    const topActionsMarkup = component.slice(topActionsStart, headingStart)

    expect(topActionsStart).toBeGreaterThan(-1)
    expect(topActionsStart).toBeLessThan(headingStart)
    expect(topActionsMarkup).toContain("Choose another target")
    expect(topActionsMarkup).toContain("Review investigation")
  })

  it("sizes result sections from their content and scrolls the panel", () => {
    const panelRule = ruleFor(".result-panel")

    expect(panelRule).toMatch(/display:\s*grid/)
    expect(panelRule).toMatch(/grid-auto-rows:\s*max-content/)
    expect(panelRule).toMatch(/overflow-y:\s*auto/)
  })

  it("allows long comparison values to wrap inside their columns", () => {
    const comparisonCellRule = ruleFor(".comparison-row > *")

    expect(comparisonCellRule).toMatch(/min-width:\s*0/)
    expect(comparisonCellRule).toMatch(/overflow-wrap:\s*anywhere/)
  })
})
