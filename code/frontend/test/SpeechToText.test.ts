import { describe, expect, it, vi } from 'vitest'
import { multiLingualSpeechRecognizer } from "../src/util/SpeechToText.js";

global.fetch = vi.fn();
const createFetchResponse = (ok, data) => {
  return { ok: ok, json: () => new Promise((resolve) => resolve(data)) };
};

describe("SpeechToText", () => {

  it("creates a speech recognizer with multiple languages", async () => {
    const languages = ["en-US", "fr-FR", "de-DE", "it-IT"];
    const token = "token";
    const region = "region";

    const response = {
      token: token,
      region: region,
      languages: languages
    };

    fetch.mockResolvedValue(createFetchResponse(true, response));

    const recognizer = await multiLingualSpeechRecognizer();

    expect(recognizer.authorizationToken).to.equal(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.equal(languages.join(","));
  });

  it("creates a speech recognizer without configured languages if language config empty array", async () => {
    const token = "token";
    const region = "region";

    const response = {
      token: token,
      region: region,
      languages: [""]
    };

    fetch.mockResolvedValue(createFetchResponse(true, response));

    const recognizer = await multiLingualSpeechRecognizer();

    expect(recognizer.authorizationToken).to.equal(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.be.undefined;
  });

  it("throws an error if speech config response not ok", async () => {
    fetch.mockResolvedValue(createFetchResponse(false, {}));

    expect(async () => await multiLingualSpeechRecognizer()).rejects.toThrowError("Network response was not ok");
  });

  it("throws an error if speech config fetching fails with an error", async () => {
    fetch.mockImplementationOnce(() => { throw new Error("Random error"); });

    expect(async () => await multiLingualSpeechRecognizer()).rejects.toThrowError("Random error");
  });
});
