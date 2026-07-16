/**
 * Vitest suite for the admin Configuration page. Mocks
 * `src/api/admin.tsx` so each scenario (loading / loaded / dirty /
 * saving / save success / save failure) is asserted against the
 * typed client surface without hitting the network..
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  Configuration,
} from "@/pages/admin/Configuration/Configuration";
import {
  AdminApiError,
  getAdminConfig,
  getAssistantTypePresets,
  patchAdminConfig,
  resetAdminConfig,
} from "@/api/admin";
import type {
  AdminConfig,
  RuntimeConfig,
} from "@/models/admin";

vi.mock("@/api/admin", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/admin")>();
  return {
    ...actual,
    getAdminConfig: vi.fn(),
    getAssistantTypePresets: vi.fn(),
    patchAdminConfig: vi.fn(),
    resetAdminConfig: vi.fn(),
  };
});

const getMock = vi.mocked(getAdminConfig);
const presetsMock = vi.mocked(getAssistantTypePresets);
const patchMock = vi.mocked(patchAdminConfig);
const resetMock = vi.mocked(resetAdminConfig);

const CONFIG_FIXTURE: AdminConfig = {
  orchestrator_name: "langgraph",
  openai_temperature: 0.0,
  openai_max_tokens: 4096,
  search_use_semantic_search: true,
  search_top_k: 5,
  log_level: "INFO",
  content_safety_enabled: false,
  cwyd_agent_instructions: "You are the Chat With Your Data assistant.",
  ai_assistant_type: "default",
  post_answering_prompt: "",
  post_answering_enabled: false,
  post_answering_filter_message: "",
};

const PATCHED_CONFIG_FIXTURE: AdminConfig = {
  ...CONFIG_FIXTURE,
  orchestrator_name: "agent_framework",
  openai_temperature: 0.7,
};

const RUNTIME_FIXTURE: RuntimeConfig = {
  orchestrator_name: "agent_framework",
  openai_temperature: 0.7,
  openai_max_tokens: null,
  search_use_semantic_search: null,
  search_top_k: null,
  log_level: null,
  content_safety_enabled: null,
  cwyd_agent_instructions: null,
  ai_assistant_type: null,
  post_answering_prompt: null,
  post_answering_enabled: null,
  post_answering_filter_message: null,
  updated_at: "2026-06-03T11:00:00Z",
  updated_by: "admin-user-id",
};

// The static `{ assistantType: personaBody }` map the dropdown uses to
// repopulate the System prompt textarea. `default` matches
// `CONFIG_FIXTURE.cwyd_agent_instructions` so re-selecting it is a
// round-trip; `contract assistant` is distinct so a switch is visible.
const PRESETS_FIXTURE = {
  default: "You are the Chat With Your Data assistant.",
  "contract assistant": "You are an AI Contract Assistant.",
  "employee assistant": "You are an AI HR Assistant.",
};

beforeEach(() => {
  getMock.mockReset();
  presetsMock.mockReset();
  presetsMock.mockResolvedValue(PRESETS_FIXTURE);
  patchMock.mockReset();
  resetMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Configuration -- page shell", () => {
  it("renders the page heading and the Runtime settings section header", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    expect(
      screen.getByRole("heading", { name: /configuration/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /runtime settings/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(1);
    });
  });
});

describe("Configuration -- initial load", () => {
  it("fires getAdminConfig on mount and renders one row per writable field", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(getMock).toHaveBeenCalledWith();
    for (const key of [
      "orchestrator_name",
      "openai_temperature",
      "openai_max_tokens",
      "search_use_semantic_search",
      "search_top_k",
      "log_level",
      "content_safety_enabled",
      "ai_assistant_type",
      "cwyd_agent_instructions",
      "post_answering_enabled",
      "post_answering_prompt",
      "post_answering_filter_message",
    ]) {
      expect(screen.getByTestId(`config-field-${key}`)).toBeInTheDocument();
      expect(screen.getByTestId(`config-input-${key}`)).toBeInTheDocument();
    }
  });

  it("populates each input with the server-supplied value", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const orchestratorSelect = screen.getByTestId(
      "config-input-orchestrator_name",
    ) as HTMLSelectElement;
    expect(orchestratorSelect.value).toBe("langgraph");
    const temperatureInput = screen.getByTestId(
      "config-input-openai_temperature",
    ) as HTMLInputElement;
    expect(temperatureInput.value).toBe("0");
    const maxTokensInput = screen.getByTestId(
      "config-input-openai_max_tokens",
    ) as HTMLInputElement;
    expect(maxTokensInput.value).toBe("4096");
    const semanticSwitch = screen.getByTestId(
      "config-input-search_use_semantic_search",
    ) as HTMLInputElement;
    expect(semanticSwitch.checked).toBe(true);
  });

  it("renders the orchestrator field as a dropdown of the known orchestrator keys", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const orchestratorSelect = screen.getByTestId(
      "config-input-orchestrator_name",
    ) as HTMLSelectElement;
    expect(orchestratorSelect.tagName).toBe("SELECT");
    expect(
      Array.from(orchestratorSelect.options).map((option) => option.value),
    ).toEqual(["langgraph", "agent_framework"]);
    expect(orchestratorSelect.value).toBe("langgraph");
  });

  it("renders the log level field as a dropdown of the known log levels", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const logLevelSelect = screen.getByTestId(
      "config-input-log_level",
    ) as HTMLSelectElement;
    expect(logLevelSelect.tagName).toBe("SELECT");
    expect(
      Array.from(logLevelSelect.options).map((option) => option.value),
    ).toEqual(["DEBUG", "INFO", "WARNING", "ERROR"]);
    expect(logLevelSelect.value).toBe("INFO");
  });

  it("renders the assistant type field as a dropdown of the known presets", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const assistantSelect = screen.getByTestId(
      "config-input-ai_assistant_type",
    ) as HTMLSelectElement;
    expect(assistantSelect.tagName).toBe("SELECT");
    expect(
      Array.from(assistantSelect.options).map((option) => option.value),
    ).toEqual(["default", "contract assistant", "employee assistant"]);
    expect(assistantSelect.value).toBe("default");
  });

  it("defaults the assistant type dropdown to 'default' when the server omits the field", async () => {
    // Simulate a backend that predates the Assistant-type presets and
    // therefore returns a config with no `ai_assistant_type`. The
    // dropdown must still land on the default preset, never an empty
    // phantom option.
    const staleConfig: AdminConfig = { ...CONFIG_FIXTURE };
    delete (staleConfig as { ai_assistant_type?: string }).ai_assistant_type;
    getMock.mockResolvedValueOnce(staleConfig);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const assistantSelect = screen.getByTestId(
      "config-input-ai_assistant_type",
    ) as HTMLSelectElement;
    expect(assistantSelect.value).toBe("default");
    expect(
      Array.from(assistantSelect.options).map((option) => option.value),
    ).toEqual(["default", "contract assistant", "employee assistant"]);
  });

  it("renders human-readable labels without the internal config-key suffix", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    // The human-readable label shows, but the raw config key never leaks
    // into the UI.
    const orchestratorField = screen.getByTestId(
      "config-field-orchestrator_name",
    );
    expect(orchestratorField).toHaveTextContent("Orchestrator");
    expect(orchestratorField).not.toHaveTextContent("(orchestrator_name)");
    const contentSafetyField = screen.getByTestId(
      "config-field-content_safety_enabled",
    );
    expect(contentSafetyField).toHaveTextContent("Content safety");
    expect(contentSafetyField).not.toHaveTextContent(
      "(content_safety_enabled)",
    );
  });

  it("shows the loading state before the GET resolves", async () => {
    let resolveGet: (value: AdminConfig) => void = () => {};
    getMock.mockReturnValueOnce(
      new Promise<AdminConfig>((resolve) => {
        resolveGet = resolve;
      }),
    );

    render(<Configuration />);

    expect(screen.getByTestId("config-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("config-form")).not.toBeInTheDocument();
    // Resolve the still-pending promise and let React flush the
    // state update so test cleanup leaves no act() warnings.
    resolveGet(CONFIG_FIXTURE);
    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
  });

  it("surfaces the load failure message and retry button on GET rejection", async () => {
    getMock.mockRejectedValueOnce(new Error("getAdminConfig: 503"));

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-load-error")).toHaveTextContent(
        /503/,
      );
    });
    expect(screen.getByTestId("config-load-retry")).toBeInTheDocument();
    expect(screen.queryByTestId("config-form")).not.toBeInTheDocument();
  });

  it("re-fires getAdminConfig when the load retry button is clicked", async () => {
    getMock.mockRejectedValueOnce(new Error("getAdminConfig: 503"));
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-load-retry")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("config-load-retry"));

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    expect(getMock).toHaveBeenCalledTimes(2);
  });
});

describe("Configuration -- form editing", () => {
  it("keeps Save and Discard disabled when the form is clean", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (
        screen.getByTestId("config-discard-button") as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("enables Save once any field is edited", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(
      (
        screen.getByTestId("config-discard-button") as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it("reverts edits when Discard is clicked", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    fireEvent.click(screen.getByTestId("config-discard-button"));

    const orchestratorSelect = screen.getByTestId(
      "config-input-orchestrator_name",
    ) as HTMLSelectElement;
    expect(orchestratorSelect.value).toBe("langgraph");
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("surfaces a per-field validation error when a required dropdown is cleared", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-log_level"), {
      target: { value: "" },
    });
    expect(
      screen.getByTestId("config-field-error-log_level"),
    ).toHaveTextContent(/must be selected/i);
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("surfaces a per-field validation error for an out-of-range temperature", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-openai_temperature"), {
      target: { value: "5" },
    });
    expect(
      screen.getByTestId("config-field-error-openai_temperature"),
    ).toHaveTextContent(/2 or less/i);
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("surfaces a 'must be a number' error when a numeric field is emptied", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-openai_max_tokens"), {
      target: { value: "" },
    });
    expect(
      screen.getByTestId("config-field-error-openai_max_tokens"),
    ).toHaveTextContent(/must be a number/i);
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});

describe("Configuration -- save flow", () => {
  it("PATCHes only the changed fields (RFC 7396 delta) and reports success", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(PATCHED_CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    fireEvent.change(screen.getByTestId("config-input-openai_temperature"), {
      target: { value: "0.7" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({
      orchestrator_name: "agent_framework",
      openai_temperature: 0.7,
    });
    await waitFor(() => {
      expect(screen.getByTestId("config-save-status")).toHaveTextContent(
        /saved/i,
      );
    });
    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it("PATCHes log_level when a different level is selected", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-log_level"), {
      target: { value: "DEBUG" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({ log_level: "DEBUG" });
  });

  it("surfaces the audit footer with the runtime updated_at / updated_by metadata after save", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(PATCHED_CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("config-audit-footer")).toBeInTheDocument();
    });
    const footer = screen.getByTestId("config-audit-footer");
    expect(footer).toHaveTextContent("2026-06-03T11:00:00Z");
    expect(footer).toHaveTextContent("admin-user-id");
  });

  it("re-syncs the form to the refreshed server config after save", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(PATCHED_CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("config-save-status")).toBeInTheDocument();
    });
    expect(
      (
        screen.getByTestId(
          "config-input-orchestrator_name",
        ) as HTMLInputElement
      ).value,
    ).toBe("agent_framework");
    // Form is now clean against the refreshed server config.
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("surfaces the failure message when the PATCH rejects", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(new Error("patchAdminConfig: 422"));

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-orchestrator_name"), {
      target: { value: "agent_framework" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("config-save-error")).toHaveTextContent(
        /422/,
      );
    });
    // Form stays dirty so the operator can fix + retry.
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("re-fires getAdminConfig when the Reload button is clicked", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    getMock.mockResolvedValueOnce(PATCHED_CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("config-reload-button"));

    await waitFor(() => {
      expect(
        (
          screen.getByTestId(
            "config-input-orchestrator_name",
          ) as HTMLInputElement
        ).value,
      ).toBe("agent_framework");
    });
    expect(getMock).toHaveBeenCalledTimes(2);
  });
});

describe("Configuration -- post-answering trio", () => {
  it("renders the post-answering prompt as a <textarea> and the other two as Input + Switch", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const promptInput = screen.getByTestId(
      "config-input-post_answering_prompt",
    );
    expect(promptInput.tagName).toBe("TEXTAREA");
    const filterInput = screen.getByTestId(
      "config-input-post_answering_filter_message",
    );
    expect(filterInput.tagName).toBe("INPUT");
    const enabledSwitch = screen.getByTestId(
      "config-input-post_answering_enabled",
    ) as HTMLInputElement;
    expect(enabledSwitch.type).toBe("checkbox");
    expect(enabledSwitch.checked).toBe(false);
  });

  it("accepts empty strings for the two post-answering text fields without surfacing a validation error", async () => {
    getMock.mockResolvedValueOnce({
      ...CONFIG_FIXTURE,
      post_answering_prompt: "Validate: {question} / {answer} / {sources}",
      post_answering_filter_message: "Sorry, that was not grounded.",
    });

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_prompt"),
      { target: { value: "" } },
    );
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_filter_message"),
      { target: { value: "" } },
    );
    expect(
      screen.queryByTestId("config-field-error-post_answering_prompt"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId(
        "config-field-error-post_answering_filter_message",
      ),
    ).not.toBeInTheDocument();
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("PATCHes the three post-answering fields when edited together", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_prompt"),
      {
        target: {
          value: "Validate {question} given {answer} and {sources}.",
        },
      },
    );
    fireEvent.click(screen.getByTestId("config-input-post_answering_enabled"));
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_filter_message"),
      { target: { value: "Sorry, that was not grounded." } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({
      post_answering_prompt:
        "Validate {question} given {answer} and {sources}.",
      post_answering_enabled: true,
      post_answering_filter_message: "Sorry, that was not grounded.",
    });
  });

  it("surfaces a 422 RAI rejection inline on the post_answering_prompt row and suppresses the generic banner", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 422, {
        detail: {
          msg: "RAI safety check rejected the submitted prompt",
          field: "post_answering_prompt",
          reason: "rai_blocked",
        },
      }),
    );

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_prompt"),
      { target: { value: "unsafe prompt body" } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    const rejection = await screen.findByTestId(
      "config-field-rai-post_answering_prompt",
    );
    expect(rejection).toHaveTextContent("rai_blocked");
    expect(
      screen.queryByTestId("config-save-error"),
    ).not.toBeInTheDocument();
    // The dirty draft is retained so the operator can revise.
    expect(
      (
        screen.getByTestId(
          "config-input-post_answering_prompt",
        ) as HTMLTextAreaElement
      ).value,
    ).toBe("unsafe prompt body");
  });

  it("falls back to the generic save-error banner when a 422 targets a non-RAI-guarded field", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 422, {
        detail: {
          msg: "value out of range",
          field: "openai_temperature",
          reason: "out_of_range",
        },
      }),
    );

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-openai_temperature"), {
      target: { value: "1.5" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("config-save-error")).toHaveTextContent(
        /422/,
      );
    });
    expect(
      screen.queryByTestId("config-field-rai-post_answering_prompt"),
    ).not.toBeInTheDocument();
  });

  it("clears the inline RAI rejection when the offending field is edited again", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockRejectedValueOnce(
      new AdminApiError("patchAdminConfig", 422, {
        detail: {
          msg: "RAI safety check rejected the submitted prompt",
          field: "post_answering_prompt",
          reason: "rai_blocked",
        },
      }),
    );

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_prompt"),
      { target: { value: "unsafe" } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    await screen.findByTestId("config-field-rai-post_answering_prompt");
    fireEvent.change(
      screen.getByTestId("config-input-post_answering_prompt"),
      { target: { value: "safer version" } },
    );
    expect(
      screen.queryByTestId("config-field-rai-post_answering_prompt"),
    ).not.toBeInTheDocument();
  });
});

describe("Configuration -- system prompt (folded from PromptEditor)", () => {
  it("renders the cwyd_agent_instructions field as a multi-line <textarea> seeded with the server value", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const promptInput = screen.getByTestId(
      "config-input-cwyd_agent_instructions",
    ) as HTMLTextAreaElement;
    expect(promptInput.tagName).toBe("TEXTAREA");
    expect(promptInput.value).toBe(CONFIG_FIXTURE.cwyd_agent_instructions);
  });

  it("accepts an empty system prompt without a validation error (clear + Save reverts to the built-in default)", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-cwyd_agent_instructions"),
      { target: { value: "" } },
    );
    expect(
      screen.queryByTestId("config-field-error-cwyd_agent_instructions"),
    ).not.toBeInTheDocument();
    expect(
      (screen.getByTestId("config-save-button") as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("PATCHes cwyd_agent_instructions when the system prompt is edited", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-cwyd_agent_instructions"),
      { target: { value: "Operator override prompt." } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({
      cwyd_agent_instructions: "Operator override prompt.",
    });
  });

  it("surfaces a 422 RAI rejection inline on the cwyd_agent_instructions row and suppresses the generic banner", async () => {
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

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-cwyd_agent_instructions"),
      { target: { value: "unsafe system prompt" } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    const rejection = await screen.findByTestId(
      "config-field-rai-cwyd_agent_instructions",
    );
    expect(rejection).toHaveTextContent("rai_blocked");
    expect(
      screen.queryByTestId("config-save-error"),
    ).not.toBeInTheDocument();
    // The dirty draft is retained so the operator can revise.
    expect(
      (
        screen.getByTestId(
          "config-input-cwyd_agent_instructions",
        ) as HTMLTextAreaElement
      ).value,
    ).toBe("unsafe system prompt");
  });

  it("clears the inline RAI rejection when the system prompt is edited again", async () => {
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

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(
      screen.getByTestId("config-input-cwyd_agent_instructions"),
      { target: { value: "unsafe" } },
    );
    fireEvent.click(screen.getByTestId("config-save-button"));

    await screen.findByTestId("config-field-rai-cwyd_agent_instructions");
    fireEvent.change(
      screen.getByTestId("config-input-cwyd_agent_instructions"),
      { target: { value: "safer system prompt" } },
    );
    expect(
      screen.queryByTestId("config-field-rai-cwyd_agent_instructions"),
    ).not.toBeInTheDocument();
  });
});

describe("Configuration -- assistant type presets", () => {
  it("renders the assistant type select seeded with the server value and the three preset options", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    const select = screen.getByTestId(
      "config-input-ai_assistant_type",
    ) as HTMLSelectElement;
    expect(select.value).toBe("default");
    const optionValues = Array.from(select.querySelectorAll("option")).map(
      (option) => option.value,
    );
    expect(optionValues).toEqual([
      "default",
      "contract assistant",
      "employee assistant",
    ]);
  });

  it("loads the selected preset body into the System prompt when the assistant type changes", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    // Presets ride the mount load (Promise.all with getAdminConfig), so
    // by the time the form renders the dropdown change can repopulate
    // the textarea from the in-state preset map.
    fireEvent.change(screen.getByTestId("config-input-ai_assistant_type"), {
      target: { value: "contract assistant" },
    });

    expect(
      (
        screen.getByTestId(
          "config-input-ai_assistant_type",
        ) as HTMLSelectElement
      ).value,
    ).toBe("contract assistant");
    expect(
      (
        screen.getByTestId(
          "config-input-cwyd_agent_instructions",
        ) as HTMLTextAreaElement
      ).value,
    ).toBe(PRESETS_FIXTURE["contract assistant"]);
  });

  it("PATCHes both ai_assistant_type and the loaded prompt when the type is switched and saved", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    patchMock.mockResolvedValueOnce(RUNTIME_FIXTURE);
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("config-input-ai_assistant_type"), {
      target: { value: "contract assistant" },
    });
    fireEvent.click(screen.getByTestId("config-save-button"));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith({
      ai_assistant_type: "contract assistant",
      cwyd_agent_instructions: PRESETS_FIXTURE["contract assistant"],
    });
  });
});

describe("Configuration -- field tooltips", () => {
  const ALL_FIELD_KEYS = [
    "ai_assistant_type",
    "cwyd_agent_instructions",
    "orchestrator_name",
    "openai_temperature",
    "openai_max_tokens",
    "search_use_semantic_search",
    "search_top_k",
    "log_level",
    "content_safety_enabled",
    "post_answering_enabled",
    "post_answering_prompt",
    "post_answering_filter_message",
  ];

  it("renders an info tooltip affordance on every configuration field", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    for (const key of ALL_FIELD_KEYS) {
      const field = screen.getByTestId(`config-field-${key}`);
      // The info tooltip trigger is the only <button> inside a field row.
      expect(within(field).getByRole("button")).toBeInTheDocument();
    }
  });

  it("renders the field's tooltip text in the DOM", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    // The CSS-only tooltip span is always present in the DOM; visibility is
    // controlled by :hover via CSS (not testable in JSDOM). Verify the text
    // is rendered and the trigger button carries the accessible aria-label.
    const field = screen.getByTestId("config-field-ai_assistant_type");
    expect(
      within(field).getByRole("tooltip"),
    ).toHaveTextContent(/Choose which persona preset/i);
    expect(
      within(field).getByRole("button", { name: /Choose which persona preset/i }),
    ).toBeInTheDocument();
  });
});

describe("Configuration -- reset to default", () => {
  const DEFAULTS_RUNTIME: RuntimeConfig = {
    orchestrator_name: null,
    openai_temperature: null,
    openai_max_tokens: null,
    search_use_semantic_search: null,
    search_top_k: null,
    log_level: null,
    content_safety_enabled: null,
    cwyd_agent_instructions: null,
    ai_assistant_type: null,
    post_answering_prompt: null,
    post_answering_enabled: null,
    post_answering_filter_message: null,
    updated_at: "2026-06-11T09:00:00Z",
    updated_by: "admin-user-id",
  };

  // With every override cleared, the effective orchestrator falls back
  // to the built-in default (agent_framework).
  const DEFAULTS_CONFIG: AdminConfig = {
    ...CONFIG_FIXTURE,
    orchestrator_name: "agent_framework",
  };

  it("renders the Reset to default button and keeps the confirm dialog closed until clicked", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    expect(screen.getByTestId("config-reset-button")).toBeInTheDocument();
    expect(
      screen.queryByTestId("config-reset-dialog"),
    ).not.toBeInTheDocument();
  });

  it("opens the destructive-confirm dialog without calling resetAdminConfig", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("config-reset-button"));

    expect(screen.getByTestId("config-reset-dialog")).toBeInTheDocument();
    expect(
      screen.getByTestId("config-reset-confirm-button"),
    ).toBeInTheDocument();
    expect(resetMock).not.toHaveBeenCalled();
  });

  it("cancelling the confirm dialog closes it and never calls resetAdminConfig", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("config-reset-button"));
    fireEvent.click(screen.getByTestId("config-reset-cancel-button"));

    expect(
      screen.queryByTestId("config-reset-dialog"),
    ).not.toBeInTheDocument();
    expect(resetMock).not.toHaveBeenCalled();
  });

  it("confirming clears every override and re-syncs the form to the resolved defaults", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    resetMock.mockResolvedValueOnce(DEFAULTS_RUNTIME);
    getMock.mockResolvedValueOnce(DEFAULTS_CONFIG);

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    expect(
      (
        screen.getByTestId(
          "config-input-orchestrator_name",
        ) as HTMLInputElement
      ).value,
    ).toBe("langgraph");

    fireEvent.click(screen.getByTestId("config-reset-button"));
    fireEvent.click(screen.getByTestId("config-reset-confirm-button"));

    await waitFor(() => {
      expect(resetMock).toHaveBeenCalledTimes(1);
    });
    expect(resetMock).toHaveBeenCalledWith();
    await waitFor(() => {
      expect(
        (
          screen.getByTestId(
            "config-input-orchestrator_name",
          ) as HTMLInputElement
        ).value,
      ).toBe("agent_framework");
    });
    // mount + post-reset refresh
    expect(getMock).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByTestId("config-reset-dialog"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("config-save-status")).toHaveTextContent(
      /saved/i,
    );
  });

  it("surfaces the failure message when resetAdminConfig rejects", async () => {
    getMock.mockResolvedValueOnce(CONFIG_FIXTURE);
    resetMock.mockRejectedValueOnce(new Error("resetAdminConfig: 403"));

    render(<Configuration />);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("config-reset-button"));
    fireEvent.click(screen.getByTestId("config-reset-confirm-button"));

    await waitFor(() => {
      expect(screen.getByTestId("config-save-error")).toHaveTextContent(
        /403/,
      );
    });
    expect(getMock).toHaveBeenCalledTimes(1);
  });
});
