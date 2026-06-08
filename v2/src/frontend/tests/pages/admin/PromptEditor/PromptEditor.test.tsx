/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest suite for the admin PromptEditor page. Mocks
 * `src/api/admin.tsx` so each scenario (loading, save success,
 * Reset-to-default, RAI rejection, generic save failure) is
 * asserted against the typed client surface without hitting the
 * network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PromptEditor } from "@/pages/admin/PromptEditor/PromptEditor";
import {
  AdminApiError,
  getAdminConfig,
  patchAdminConfig,
} from "@/api/admin";
import type { AdminConfig, RuntimeConfig } from "@/models/admin";

vi.mock("../../../../src/api/admin", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
  return {
    ...actual,
    getAdminConfig: vi.fn(),
    patchAdminConfig: vi.fn(),
  };
});

const getMock = vi.mocked(getAdminConfig);
const patchMock = vi.mocked(patchAdminConfig);

const CONFIG_FIXTURE: AdminConfig = {
  orchestrator_name: "langgraph",
  openai_temperature: 0.0,
  openai_max_tokens: 4096,
  search_use_semantic_search: true,
  search_top_k: 5,
  log_level: "INFO",
  content_safety_enabled: false,
  cwyd_agent_instructions: "You are the Chat With Your Data assistant.",
  post_answering_prompt: "",
  post_answering_enabled: false,
  post_answering_filter_message: "",
};

const OVERRIDDEN_CONFIG_FIXTURE: AdminConfig = {
  ...CONFIG_FIXTURE,
  cwyd_agent_instructions: "Operator override prompt.",
};

const RUNTIME_FIXTURE: RuntimeConfig = {
  orchestrator_name: null,
  openai_temperature: null,
  openai_max_tokens: null,
  search_use_semantic_search: null,
  search_top_k: null,
  log_level: null,
  content_safety_enabled: null,
  cwyd_agent_instructions: "Operator override prompt.",
  post_answering_prompt: null,
  post_answering_enabled: null,
  post_answering_filter_message: null,
  updated_at: "2026-06-08T10:00:00Z",
  updated_by: "admin-user-id",
};

const RUNTIME_CLEARED_FIXTURE: RuntimeConfig = {
  ...RUNTIME_FIXTURE,
  cwyd_agent_instructions: null,
  updated_at: "2026-06-08T10:01:00Z",
};

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PromptEditor -- initial load", () => {
  it("fires getAdminConfig on mount and renders the current prompt", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<PromptEditor />);

    expect(
      screen.getByRole("heading", { name: /prompt editor/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("prompt-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(1);
    });

    const textarea = screen.getByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });
    expect(textarea).toBeEnabled();
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset-default")).toBeEnabled();
    expect(screen.queryByTestId("prompt-loading")).not.toBeInTheDocument();
  });

  it("renders a retry-capable error when the initial load fails", async () => {
    getMock.mockRejectedValueOnce(new Error("getAdminConfig: 503"));

    render(<PromptEditor />);

    const errorBox = await screen.findByTestId("prompt-load-error");
    expect(errorBox).toHaveTextContent("getAdminConfig: 503");

    expect(screen.getByTestId("prompt-editor-textarea")).toBeDisabled();
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset-default")).toBeDisabled();

    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    fireEvent.click(screen.getByTestId("prompt-load-retry"));

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.getByTestId("prompt-editor-textarea")).toHaveValue(
        CONFIG_FIXTURE.cwyd_agent_instructions,
      );
    });
    expect(screen.queryByTestId("prompt-load-error")).not.toBeInTheDocument();
  });
});

describe("PromptEditor -- dirty state", () => {
  it("enables Save and Reset (revert) when the prompt is edited", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, { target: { value: "New system prompt" } });

    expect(screen.getByTestId("prompt-save")).toBeEnabled();
    expect(screen.getByTestId("prompt-reset")).toBeEnabled();
  });

  it("reverts the draft to the last-saved prompt on Reset (revert)", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, { target: { value: "Unsaved edit" } });
    fireEvent.click(screen.getByTestId("prompt-reset"));

    expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
    expect(screen.getByTestId("prompt-reset")).toBeDisabled();
  });
});

describe("PromptEditor -- save", () => {
  it("PATCHes cwyd_agent_instructions on Save and re-fetches the effective config", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(OVERRIDDEN_CONFIG_FIXTURE);

    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, {
      target: { value: "Operator override prompt." },
    });
    fireEvent.click(screen.getByTestId("prompt-save"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({
      cwyd_agent_instructions: "Operator override prompt.",
    });

    await screen.findByTestId("prompt-save-success");
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(2);
    });
    expect(textarea).toHaveValue("Operator override prompt.");
    expect(screen.getByTestId("prompt-save")).toBeDisabled();
  });

  it("surfaces a structured RAI rejection inline and keeps the dirty draft", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 422, {
        detail: {
          msg: "RAI safety check rejected the submitted prompt",
          field: "cwyd_agent_instructions",
          reason: "rai_blocked",
        },
      }),
    );

    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, { target: { value: "unsafe prompt" } });
    fireEvent.click(screen.getByTestId("prompt-save"));

    const rejection = await screen.findByTestId("prompt-rai-error");
    expect(rejection).toHaveTextContent("rai_blocked");
    expect(textarea).toHaveValue("unsafe prompt");
    expect(screen.queryByTestId("prompt-save-error")).not.toBeInTheDocument();
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("prompt-save")).toBeEnabled();
  });

  it("surfaces a generic error message on non-422 save failures", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 503, null),
    );

    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, { target: { value: "another prompt" } });
    fireEvent.click(screen.getByTestId("prompt-save"));

    const errorBox = await screen.findByTestId("prompt-save-error");
    expect(errorBox).toHaveTextContent("503");
    expect(screen.queryByTestId("prompt-rai-error")).not.toBeInTheDocument();
  });

  it("treats a 422 on a non-prompt field as a generic save error (not an RAI rejection)", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 422, {
        detail: {
          msg: "Unknown writable field",
          field: "search_top_k",
        },
      }),
    );

    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });

    fireEvent.change(textarea, { target: { value: "draft" } });
    fireEvent.click(screen.getByTestId("prompt-save"));

    await screen.findByTestId("prompt-save-error");
    expect(screen.queryByTestId("prompt-rai-error")).not.toBeInTheDocument();
  });
});

describe("PromptEditor -- reset to default", () => {
  it("PATCHes cwyd_agent_instructions: null on Reset to default", async () => {
    getMock.mockResolvedValueOnce(OVERRIDDEN_CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_CLEARED_FIXTURE);
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<PromptEditor />);

    const textarea = await screen.findByTestId("prompt-editor-textarea");
    await waitFor(() => {
      expect(textarea).toHaveValue(
        OVERRIDDEN_CONFIG_FIXTURE.cwyd_agent_instructions,
      );
    });

    fireEvent.click(screen.getByTestId("prompt-reset-default"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({ cwyd_agent_instructions: null });
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(textarea).toHaveValue(CONFIG_FIXTURE.cwyd_agent_instructions);
    });
    await screen.findByTestId("prompt-save-success");
  });
});
