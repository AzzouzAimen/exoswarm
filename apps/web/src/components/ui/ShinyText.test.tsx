import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import ShinyText from "./ShinyText"

describe("ShinyText", () => {
  it("keeps disabled animation text readable", () => {
    const markup = renderToStaticMarkup(
      <ShinyText text="Search for a repeating signal" disabled color="currentColor" />,
    )

    expect(markup).toContain("Search for a repeating signal")
    expect(markup).toContain("color:currentColor")
    expect(markup).not.toContain("-webkit-text-fill-color:transparent")
  })
})
