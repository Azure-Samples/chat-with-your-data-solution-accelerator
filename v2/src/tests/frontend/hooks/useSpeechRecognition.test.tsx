/**
 * Pillar: Stable Core
 * Phase: 4 (S1 / SPEECH-MVP)
 *
 * Vitest suite for `useSpeechRecognition`. We mock both the
 * `microsoft-cognitiveservices-speech-sdk` module and the
 * `getSpeechConfig` REST client so the hook is tested in isolation —
 * no real audio device, no real backend.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

// --- SDK mock ---------------------------------------------------------------
//
// The real SDK imports browser-only WebAssembly and audio APIs at
// module init; importing it under jsdom crashes. So we replace the
// whole module surface with a tiny set of fakes that remember which
// callbacks the hook installed and let the test fire them.
//
// `vi.mock` factories are hoisted ABOVE imports by vitest, so any
// shared mutable state has to be created in `vi.hoisted` (also
// hoisted) — top-level `const lastRecognizer = {...}` would crash
// with "Cannot access ... before initialization". See
// https://vitest.dev/api/vi.html#vi-hoisted

type RecognizerCallbacks = {
  recognizing: ((s: unknown, e: unknown) => void) | null;
  recognized: ((s: unknown, e: unknown) => void) | null;
  canceled: ((s: unknown, e: unknown) => void) | null;
};

const { lastRecognizer, sdkMock } = vi.hoisted(() => {
  const lastRecognizer: {
    callbacks: RecognizerCallbacks;
    startCalls: number;
    stopCalls: number;
    closeCalls: number;
    failStart: boolean;
  } = {
    callbacks: { recognizing: null, recognized: null, canceled: null },
    startCalls: 0,
    stopCalls: 0,
    closeCalls: 0,
    failStart: false,
  };

  class FakeSpeechRecognizer {
    set recognizing(cb: (s: unknown, e: unknown) => void) {
      lastRecognizer.callbacks.recognizing = cb;
    }
    set recognized(cb: (s: unknown, e: unknown) => void) {
      lastRecognizer.callbacks.recognized = cb;
    }
    set canceled(cb: (s: unknown, e: unknown) => void) {
      lastRecognizer.callbacks.canceled = cb;
    }
    startContinuousRecognitionAsync(
      onSuccess: () => void,
      onError: (err: string) => void,
    ): void {
      lastRecognizer.startCalls += 1;
      if (lastRecognizer.failStart) {
        onError("simulated SDK start failure");
        return;
      }
      onSuccess();
    }
    stopContinuousRecognitionAsync(
      onSuccess: () => void,
      _onError: (err: string) => void,
    ): void {
      lastRecognizer.stopCalls += 1;
      onSuccess();
    }
    close(): void {
      lastRecognizer.closeCalls += 1;
    }
    static FromConfig(): FakeSpeechRecognizer {
      return new FakeSpeechRecognizer();
    }
  }

  const sdkMock = {
    AudioConfig: { fromDefaultMicrophoneInput: () => ({}) },
    AutoDetectSourceLanguageConfig: { fromLanguages: () => ({}) },
    CancellationReason: { Error: 1, EndOfStream: 2 },
    ResultReason: { RecognizedSpeech: 3, RecognizingSpeech: 4 },
    SpeechConfig: {
      fromAuthorizationToken: () => ({ speechRecognitionLanguage: "" }),
    },
    SpeechRecognizer: FakeSpeechRecognizer,
  };

  return { lastRecognizer, sdkMock };
});

function resetRecognizerState() {
  lastRecognizer.callbacks = {
    recognizing: null,
    recognized: null,
    canceled: null,
  };
  lastRecognizer.startCalls = 0;
  lastRecognizer.stopCalls = 0;
  lastRecognizer.closeCalls = 0;
  lastRecognizer.failStart = false;
}

vi.mock("microsoft-cognitiveservices-speech-sdk", () => sdkMock);

// --- API client mock --------------------------------------------------------

vi.mock("@/api/speech", () => ({
  getSpeechConfig: vi.fn(),
}));

// Imports MUST come AFTER the vi.mock calls so vitest replaces the
// modules before the hook resolves them.
import { getSpeechConfig } from "@/api/speech";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

const getSpeechConfigMock = vi.mocked(getSpeechConfig);

beforeEach(() => {
  resetRecognizerState();
  getSpeechConfigMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useSpeechRecognition", () => {
  it("starts in an idle state", () => {
    const { result } = renderHook(() => useSpeechRecognition());
    expect(result.current.isListening).toBe(false);
    expect(result.current.transcript).toBe("");
    expect(result.current.error).toBeNull();
  });

  it("fetches /api/speech once per session and starts the recognizer", async () => {
    getSpeechConfigMock.mockResolvedValue({
      token: "spch-token",
      region: "eastus2",
      languages: ["en-US", "fr-FR"],
    });

    const { result } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });

    expect(getSpeechConfigMock).toHaveBeenCalledTimes(1);
    expect(lastRecognizer.startCalls).toBe(1);
    expect(result.current.isListening).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("appends interim and final transcript text as SDK events fire", async () => {
    getSpeechConfigMock.mockResolvedValue({
      token: "spch-token",
      region: "eastus2",
      languages: ["en-US"],
    });

    const { result } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });

    // Interim
    act(() => {
      lastRecognizer.callbacks.recognizing!(null, {
        result: { text: "hel", reason: 4 },
      });
    });
    expect(result.current.transcript).toBe("hel");

    // Final segment commits + leaves a trailing space
    act(() => {
      lastRecognizer.callbacks.recognized!(null, {
        result: { text: "hello", reason: 3 },
      });
    });
    expect(result.current.transcript).toBe("hello ");

    // Next interim builds on the committed final
    act(() => {
      lastRecognizer.callbacks.recognizing!(null, {
        result: { text: "wo", reason: 4 },
      });
    });
    expect(result.current.transcript).toBe("hello wo");
  });

  it("stops the recognizer and clears isListening on stop()", async () => {
    getSpeechConfigMock.mockResolvedValue({
      token: "t",
      region: "eastus2",
      languages: ["en-US"],
    });

    const { result } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.isListening).toBe(true);

    await act(async () => {
      await result.current.stop();
    });

    expect(lastRecognizer.stopCalls).toBe(1);
    expect(lastRecognizer.closeCalls).toBe(1);
    expect(result.current.isListening).toBe(false);
  });

  it("surfaces token-fetch failures as `error` and never throws", async () => {
    getSpeechConfigMock.mockRejectedValue(new Error("status 503"));

    const { result } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.isListening).toBe(false);
    expect(result.current.error).toMatch(/503/);
    expect(lastRecognizer.startCalls).toBe(0);
  });

  it("surfaces SDK canceled events as `error` and stops listening", async () => {
    getSpeechConfigMock.mockResolvedValue({
      token: "t",
      region: "eastus2",
      languages: ["en-US"],
    });

    const { result } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });

    await act(async () => {
      lastRecognizer.callbacks.canceled!(null, {
        reason: 1,
        errorDetails: "mic permission denied",
      });
    });

    await waitFor(() => expect(result.current.isListening).toBe(false));
    expect(result.current.error).toBe("mic permission denied");
  });

  it("tears down the recognizer on unmount", async () => {
    getSpeechConfigMock.mockResolvedValue({
      token: "t",
      region: "eastus2",
      languages: ["en-US"],
    });

    const { result, unmount } = renderHook(() => useSpeechRecognition());
    await act(async () => {
      await result.current.start();
    });
    expect(lastRecognizer.stopCalls).toBe(0);

    unmount();
    // Unmount cleanup is fire-and-forget; give the microtask queue a
    // chance to drain so stop/close calls are observable.
    await Promise.resolve();
    expect(lastRecognizer.stopCalls).toBe(1);
    expect(lastRecognizer.closeCalls).toBe(1);
  });
});
