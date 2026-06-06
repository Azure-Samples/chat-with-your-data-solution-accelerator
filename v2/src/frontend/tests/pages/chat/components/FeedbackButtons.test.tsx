/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest + @testing-library/react suite for FeedbackButtons.
 * Pure presentational tests -- no fetch involvement; the
 * `onSubmit` prop is a `vi.fn()` so we can assert what feedback
 * string the parent receives.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FeedbackButtons } from "@/pages/chat/components/FeedbackButtons";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FeedbackButtons", () => {
  it("renders both thumb buttons with accessible labels", () => {
    render(
      <FeedbackButtons messageId="m1" onSubmit={vi.fn()} />,
    );

    expect(screen.getByTestId("feedback-m1")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-m1-positive")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-m1-negative")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Good response" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Bad response" }),
    ).toBeInTheDocument();
  });

  it("does not render the reason form on initial mount", () => {
    render(<FeedbackButtons messageId="m1" onSubmit={vi.fn()} />);
    expect(
      screen.queryByTestId("feedback-m1-reason-form"),
    ).not.toBeInTheDocument();
  });

  it("reports neither thumb as pressed when feedback is undefined", () => {
    render(<FeedbackButtons messageId="m1" onSubmit={vi.fn()} />);
    expect(screen.getByTestId("feedback-m1-positive")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("feedback-m1-negative")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("marks 👍 as pressed when feedback is exactly 'positive'", () => {
    render(
      <FeedbackButtons
        messageId="m1"
        feedback="positive"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("feedback-m1-positive")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("feedback-m1-negative")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("marks 👎 as pressed when feedback starts with 'negative'", () => {
    render(
      <FeedbackButtons
        messageId="m1"
        feedback="negative: missing context"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("feedback-m1-negative")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("feedback-m1-positive")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("treats feedback === null as unset", () => {
    render(
      <FeedbackButtons messageId="m1" feedback={null} onSubmit={vi.fn()} />,
    );
    expect(screen.getByTestId("feedback-m1-positive")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("feedback-m1-negative")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("calls onSubmit('positive') when 👍 is clicked from an unset state", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-positive"));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("positive");
  });

  it("does NOT call onSubmit when 👍 is clicked while already positive", () => {
    const onSubmit = vi.fn();
    render(
      <FeedbackButtons
        messageId="m1"
        feedback="positive"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByTestId("feedback-m1-positive"));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("opens the reason form when 👎 is clicked from an unset state", () => {
    const onSubmit = vi.fn();
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));

    expect(
      screen.getByTestId("feedback-m1-reason-form"),
    ).toBeInTheDocument();
    // 👎 click alone does not submit feedback; the user must press Send.
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does NOT open the reason form when 👎 is clicked while already negative", () => {
    render(
      <FeedbackButtons
        messageId="m1"
        feedback="negative"
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));

    expect(
      screen.queryByTestId("feedback-m1-reason-form"),
    ).not.toBeInTheDocument();
  });

  it("submits 'negative' (no colon) when the reason textarea is left blank", () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    fireEvent.click(screen.getByTestId("feedback-m1-reason-submit"));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("negative");
  });

  it("submits 'negative: <reason>' when the textarea has a value", () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    fireEvent.change(screen.getByTestId("feedback-m1-reason-input"), {
      target: { value: "  missing citation  " },
    });
    fireEvent.click(screen.getByTestId("feedback-m1-reason-submit"));

    expect(onSubmit).toHaveBeenCalledWith("negative: missing citation");
  });

  it("closes the reason form after Send", () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    fireEvent.click(screen.getByTestId("feedback-m1-reason-submit"));

    expect(
      screen.queryByTestId("feedback-m1-reason-form"),
    ).not.toBeInTheDocument();
  });

  it("closes the reason form on Cancel without calling onSubmit", () => {
    const onSubmit = vi.fn();
    render(<FeedbackButtons messageId="m1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    fireEvent.change(screen.getByTestId("feedback-m1-reason-input"), {
      target: { value: "typed but cancelled" },
    });
    fireEvent.click(screen.getByTestId("feedback-m1-reason-cancel"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      screen.queryByTestId("feedback-m1-reason-form"),
    ).not.toBeInTheDocument();
  });

  it("clears the textarea between consecutive open / cancel cycles", () => {
    render(<FeedbackButtons messageId="m1" onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    fireEvent.change(screen.getByTestId("feedback-m1-reason-input"), {
      target: { value: "first attempt" },
    });
    fireEvent.click(screen.getByTestId("feedback-m1-reason-cancel"));

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    expect(
      (screen.getByTestId("feedback-m1-reason-input") as HTMLTextAreaElement)
        .value,
    ).toBe("");
  });

  it("caps the reason textarea via maxLength to fit the backend body limit", () => {
    render(<FeedbackButtons messageId="m1" onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByTestId("feedback-m1-negative"));
    const input = screen.getByTestId(
      "feedback-m1-reason-input",
    ) as HTMLTextAreaElement;
    expect(input.maxLength).toBe(53);
  });

  it("disables both thumb buttons when disabled=true", () => {
    render(
      <FeedbackButtons messageId="m1" onSubmit={vi.fn()} disabled={true} />,
    );

    expect(screen.getByTestId("feedback-m1-positive")).toBeDisabled();
    expect(screen.getByTestId("feedback-m1-negative")).toBeDisabled();
  });

  it("does not call onSubmit when 👍 is clicked while disabled", () => {
    const onSubmit = vi.fn();
    render(
      <FeedbackButtons messageId="m1" onSubmit={onSubmit} disabled={true} />,
    );

    fireEvent.click(screen.getByTestId("feedback-m1-positive"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("renders distinct test ids per messageId so multiple instances coexist", () => {
    render(
      <div>
        <FeedbackButtons messageId="m1" onSubmit={vi.fn()} />
        <FeedbackButtons messageId="m2" onSubmit={vi.fn()} />
      </div>,
    );
    expect(screen.getByTestId("feedback-m1-positive")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-m2-positive")).toBeInTheDocument();
  });
});
