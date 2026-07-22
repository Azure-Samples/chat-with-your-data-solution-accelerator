/**
 * React hook wrapping `microsoft-cognitiveservices-speech-sdk` for
 * browser-side multi-lingual speech-to-text. The backend (`/api/speech`)
 * mints a 10-minute AAD-bearer authorization token; the hook hands
 * that token to the SDK and exposes a tiny `{isListening, transcript,
 * error, start, stop}` surface to consumers.
 *
 * Behaviour:
 *
 *   - `start()` lazily fetches a Speech token, constructs the SDK's
 *     `SpeechRecognizer`, starts continuous recognition, and wires
 *     `recognizing` (interim) + `recognized` (final) events to update
 *     `transcript`. Interim updates replace the running tail of
 *     `transcript`; final updates commit + leave a trailing space so
 *     the next interim doesn't clobber the previous final.
 *
 *   - `stop()` stops continuous recognition and closes the recognizer.
 *     Idempotent -- calling `stop()` while not listening is a no-op.
 *
 *   - On any error (token fetch, SDK construction, recognizer
 *     `canceled` event), the hook flips `error` to a human-readable
 *     string and stops listening. It NEVER throws -- the consumer can
 *     safely render `{error}` and disable the mic button.
 *
 *   - Cleanup: an unmount while the recognizer is alive triggers
 *     `stop()` synchronously via `useEffect` cleanup so we don't leak
 *     the underlying audio stream.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AudioConfig,
  AutoDetectSourceLanguageConfig,
  CancellationReason,
  ResultReason,
  SpeechConfig,
  SpeechRecognizer,
  type SpeechRecognitionEventArgs,
  type SpeechRecognitionCanceledEventArgs,
} from "microsoft-cognitiveservices-speech-sdk";

import { getSpeechConfig } from "@/api/speech";

export interface UseSpeechRecognition {
  /** True between `start()` resolving and `stop()` (or an error) firing. */
  isListening: boolean;
  /** Concatenated final segments + the running interim tail. */
  transcript: string;
  /** Human-readable error string, or `null` when healthy. */
  error: string | null;
  /** Begin a recognition session. Resolves once recognition has started. */
  start: () => Promise<void>;
  /** Stop a recognition session. Resolves once cleanup is complete. */
  stop: () => Promise<void>;
}

function buildRecognizer(
  token: string,
  region: string,
  languages: string[],
): SpeechRecognizer {
  const speechConfig = SpeechConfig.fromAuthorizationToken(token, region);
  const audioConfig = AudioConfig.fromDefaultMicrophoneInput();
  if (languages.length > 1) {
    const autoDetect =
      AutoDetectSourceLanguageConfig.fromLanguages(languages);
    return SpeechRecognizer.FromConfig(speechConfig, autoDetect, audioConfig);
  }
  const [first] = languages;
  if (first !== undefined) {
    speechConfig.speechRecognitionLanguage = first;
  }
  return new SpeechRecognizer(speechConfig, audioConfig);
}

export function useSpeechRecognition(): UseSpeechRecognition {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Mutable refs (not state) for SDK plumbing -- we don't want a
  // re-render every time the recognizer's reference changes, only
  // when surface state (`isListening` / `transcript` / `error`) does.
  const recognizerRef = useRef<SpeechRecognizer | null>(null);
  const finalsRef = useRef<string>("");

  const teardownRecognizer = useCallback(async () => {
    const recognizer = recognizerRef.current;
    if (recognizer === null) return;
    recognizerRef.current = null;
    try {
      await new Promise<void>((resolve) => {
        recognizer.stopContinuousRecognitionAsync(
          () => {
            resolve();
          },
          () => {
            resolve();
          },
        );
      });
    } finally {
      recognizer.close();
    }
  }, []);

  const stop = useCallback(async () => {
    if (recognizerRef.current === null) return;
    await teardownRecognizer();
    setIsListening(false);
  }, [teardownRecognizer]);

  const start = useCallback(async () => {
    if (recognizerRef.current !== null) return;
    setError(null);
    setTranscript("");
    finalsRef.current = "";

    let recognizer: SpeechRecognizer;
    try {
      const { token, region, languages } = await getSpeechConfig();
      recognizer = buildRecognizer(token, region, languages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return;
    }

    recognizer.recognizing = (
      _sender: unknown,
      args: SpeechRecognitionEventArgs,
    ) => {
      const interim = args.result.text;
      setTranscript(finalsRef.current + interim);
    };
    recognizer.recognized = (
      _sender: unknown,
      args: SpeechRecognitionEventArgs,
    ) => {
      if (args.result.reason !== ResultReason.RecognizedSpeech) return;
      const finalText = args.result.text;
      if (finalText === "") return;
      finalsRef.current =
        finalsRef.current.length > 0
          ? `${finalsRef.current}${finalText} `
          : `${finalText} `;
      setTranscript(finalsRef.current);
    };
    recognizer.canceled = (
      _sender: unknown,
      args: SpeechRecognitionCanceledEventArgs,
    ) => {
      const message =
        args.reason === CancellationReason.Error
          ? args.errorDetails || "Speech recognition was canceled."
          : "Speech recognition was canceled.";
      setError(message);
      void teardownRecognizer().then(() => {
        setIsListening(false);
      });
    };

    recognizerRef.current = recognizer;
    await new Promise<void>((resolve, reject) => {
      recognizer.startContinuousRecognitionAsync(
        () => {
          setIsListening(true);
          resolve();
        },
        (sdkError: string) => {
          recognizerRef.current = null;
          recognizer.close();
          setError(sdkError || "Failed to start speech recognition.");
          reject(new Error(sdkError));
        },
      );
    }).catch(() => {
      // Swallow -- we've already surfaced the error via `setError`.
    });
  }, [teardownRecognizer]);

  // Unmount cleanup so we never leak the mic input.
  useEffect(() => {
    return () => {
      void teardownRecognizer();
    };
  }, [teardownRecognizer]);

  return { isListening, transcript, error, start, stop };
}
