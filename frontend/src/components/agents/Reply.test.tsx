import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Reply } from "./Reply";

afterEach(cleanup);

// The source of every file that draws an agent's words, to prove none of them can insert markup.
const sources = import.meta.glob(["./*.ts", "./*.tsx", "!./*.test.ts", "!./*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("drawing a reply", () => {
  it("shows hostile markup as text and creates no elements from it", () => {
    const hostile = '<script>alert(1)</script><img src=x onerror="alert(1)"><iframe src="x"></iframe><b>no</b>';
    const { container } = render(<Reply text={hostile} />);
    expect(container.querySelector("script, img, iframe, b, style, svg")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">');
  });

  it("makes a safe link open in a new tab without handing over the page, and names the site", () => {
    const { container } = render(<Reply text="Read [the filing](https://www.example.com/a) now" />);
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("href")).toBe("https://www.example.com/a");
    expect(anchor?.getAttribute("target")).toBe("_blank");
    expect(anchor?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(container.textContent).toContain("the filing (example.com)");
  });

  it("makes no link from a script, a data address, plain http or a link that hides a login", () => {
    const text = "[a](javascript:alert(1)) [b](data:text/html,x) [c](http://example.com) [d](https://u:p@example.com)";
    const { container } = render(<Reply text={text} />);
    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(container.textContent).toContain("[a](javascript:alert(1))");
  });

  it("draws paragraphs, line breaks, bold and lists", () => {
    const { container } = render(<Reply text={"One **two**\nthree\n\n- a\n- b\n\n## Head"} />);
    expect(container.querySelectorAll("p")).toHaveLength(2);
    expect(container.querySelector("strong")?.textContent).toBe("two");
    expect(container.querySelectorAll("br")).toHaveLength(1);
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });
});

describe("the files that draw an agent's words", () => {
  it("never use a way of inserting HTML", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(5);
    for (const [file, source] of Object.entries(sources)) {
      expect(source, file).not.toMatch(/dangerouslySetInnerHTML|innerHTML|insertAdjacentHTML|document\.write|eval\(/);
    }
  });
});
