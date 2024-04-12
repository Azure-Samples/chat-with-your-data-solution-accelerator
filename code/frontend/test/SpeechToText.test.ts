import { beforeEach, describe, expect, it } from 'vitest'
import { multiLingualSpeechRecognizer } from "../src/util/SpeechToText.js";

const recognizedLanguages = "en-US,es-ES";

describe("SpeechToText", () => {
  beforeEach(() => {
    import.meta.env.VITE_SPEECH_RECOGNIZER_LANGUAGES = recognizedLanguages;
  })

  it("creates a speech recognizer with multiple languages", async () => {
    const token = "token";
    const region = "region";
    const languages = ["en-US", "fr-FR", "de-DE", "it-IT"];
    const recognizer = multiLingualSpeechRecognizer(token, region, languages);

    expect(recognizer.authorizationToken).to.equal(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.equal(recognizedLanguages);
  });
});
