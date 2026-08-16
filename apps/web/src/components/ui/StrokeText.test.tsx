import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import StrokeText from "./StrokeText"

describe("StrokeText", () => {
  it("keeps the animated question available to assistive technology", () => {
    const markup = renderToStaticMarkup(<StrokeText text="Do the brightness dips repeat?" />)

    expect(markup).toContain('role="img"')
    expect(markup).toContain('aria-label="Do the brightness dips repeat?"')
    expect(markup).toContain("data-stroke-char")
    expect(markup).toContain("data-fill-char")
  })
})
