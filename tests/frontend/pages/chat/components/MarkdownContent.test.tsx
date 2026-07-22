/**
 * Vitest coverage for <MarkdownContent>. Asserts the markdown surface
 * the chat transcript depends on (bold, lists, headings, inline code,
 * GFM strikethrough, safe external links, plain-text passthrough) and
 * the security contract that embedded raw HTML is escaped rather than
 * mounted as live DOM.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MarkdownContent } from "@/pages/chat/components/MarkdownContent";

describe("MarkdownContent", () => {
  it("renders bold markdown as a <strong> element", () => {
    const { container } = render(
      <MarkdownContent content="hello **world**" />,
    );
    const strong = container.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe("world");
  });

  it("renders an unordered list as <ul> with <li> items", () => {
    const { container } = render(
      <MarkdownContent content={"- one\n- two"} />,
    );
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toBe("one");
    expect(items[1]?.textContent).toBe("two");
  });

  it("renders a heading as an <h1> element", () => {
    const { container } = render(<MarkdownContent content="# Title" />);
    const heading = container.querySelector("h1");
    expect(heading?.textContent).toBe("Title");
  });

  it("renders inline code as a <code> element", () => {
    const { container } = render(
      <MarkdownContent content={"run `npm test` now"} />,
    );
    const code = container.querySelector("code");
    expect(code?.textContent).toBe("npm test");
  });

  it("renders GFM strikethrough as a <del> element", () => {
    const { container } = render(<MarkdownContent content="~~gone~~" />);
    const del = container.querySelector("del");
    expect(del?.textContent).toBe("gone");
  });

  it("renders a link that opens in a new tab with a safe rel", () => {
    const { container } = render(
      <MarkdownContent content="[site](https://example.com)" />,
    );
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://example.com");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toBe("noreferrer");
    expect(link?.textContent).toBe("site");
  });

  it("renders plain text unchanged", () => {
    const { container } = render(
      <MarkdownContent content="just plain text" />,
    );
    expect(container.textContent).toContain("just plain text");
  });

  it("does not mount embedded raw HTML as live nodes (no rehype-raw)", () => {
    const { container } = render(
      <MarkdownContent content={"before <script>danger()</script> after"} />,
    );
    // Raw HTML is escaped, not parsed into live elements.
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("before");
    expect(container.textContent).toContain("after");
  });

  it("applies the optional className to the wrapper element", () => {
    const { container } = render(
      <MarkdownContent content="x" className="my-wrap" />,
    );
    const wrapper = container.querySelector(".my-wrap");
    expect(wrapper).not.toBeNull();
    expect(wrapper?.textContent).toContain("x");
  });

  it("renders a ^K^ token as a <sup> element when enableSupersub is set", () => {
    const { container } = render(
      <MarkdownContent content="the plan ^1^ works" enableSupersub />,
    );
    const sup = container.querySelector("sup");
    expect(sup).not.toBeNull();
    expect(sup?.textContent).toBe("1");
  });

  it("leaves a ^K^ token as literal text when enableSupersub is not set", () => {
    const { container } = render(
      <MarkdownContent content="the plan ^1^ works" />,
    );
    expect(container.querySelector("sup")).toBeNull();
    expect(container.textContent).toContain("^1^");
  });
});
