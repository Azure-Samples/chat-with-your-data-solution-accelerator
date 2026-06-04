/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Route-shell tests for the admin PromptEditor page.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PromptEditor } from "@/pages/admin/PromptEditor/PromptEditor";

describe("PromptEditor", () => {
  it("renders heading, textarea, and disabled action buttons", () => {
    render(<PromptEditor />);

    expect(
      screen.getByRole("heading", { name: /prompt editor/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("prompt-editor-form")).toBeInTheDocument();
    expect(screen.getByTestId("prompt-editor-textarea")).toBeInTheDocument();
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset")).toBeDisabled();
  });

  it("enables save/reset when the prompt is edited", () => {
    render(<PromptEditor />);

    fireEvent.change(screen.getByTestId("prompt-editor-textarea"), {
      target: { value: "New system prompt" },
    });

    expect(screen.getByTestId("prompt-save")).toBeEnabled();
    expect(screen.getByTestId("prompt-reset")).toBeEnabled();
  });

  it("saves prompt text to localStorage and resets dirty state", () => {
    render(<PromptEditor />);

    fireEvent.change(screen.getByTestId("prompt-editor-textarea"), {
      target: { value: "Persisted prompt" },
    });
    fireEvent.click(screen.getByTestId("prompt-save"));

    expect(
      window.localStorage.getItem("cwyd.admin.promptEditor.systemPrompt"),
    ).toBe("Persisted prompt");
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset")).toBeDisabled();
    expect(screen.getByTestId("prompt-status")).toHaveTextContent(
      "Saved locally in this browser.",
    );
  });

  it("resets the draft back to the last saved prompt", () => {
    window.localStorage.setItem(
      "cwyd.admin.promptEditor.systemPrompt",
      "Stored prompt",
    );
    render(<PromptEditor />);

    const textarea = screen.getByTestId("prompt-editor-textarea");
    expect(textarea).toHaveValue("Stored prompt");

    fireEvent.change(textarea, { target: { value: "Unsaved edit" } });
    fireEvent.click(screen.getByTestId("prompt-reset"));

    expect(textarea).toHaveValue("Stored prompt");
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset")).toBeDisabled();
  });
});
