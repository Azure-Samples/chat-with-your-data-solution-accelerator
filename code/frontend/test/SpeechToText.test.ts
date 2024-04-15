import { beforeEach, describe, expect, it } from 'vitest'
import { multiLingualSpeechRecognizer, defaultLanguage } from "../src/util/SpeechToText.js";

const recognizedLanguages = "en-US,es-ES";

describe("SpeechToText", () => {
  beforeEach(() => {

  })

  it("creates a speech recognizer with the default language if config not specified", async () => {;
    const token = "token";
    const region = "region";
    const languages = ["en-US", "fr-FR", "de-DE", "it-IT"];
    const recognizer = multiLingualSpeechRecognizer(token, region, languages);

    const recognizer = multiLingualSpeechRecognizer(key, region);

    expect(recognizer.properties.getProperty("SpeechServiceConnection_Key")).to.equal(key);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.equal(defaultLanguage);
  });

  it("creates a speech recognizer with multiple languages", async () => {
      import.meta.env.VITE_SPEECH_RECOGNIZER_LANGUAGES = recognizedLanguages;
      const key = "key";
      const region = "region";


      const recognizer = multiLingualSpeechRecognizer(key, region);

      expect(recognizer.properties.getProperty("SpeechServiceConnection_Key")).to.equal(key);
      expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
      expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.equal(recognizedLanguages);
    });
});
