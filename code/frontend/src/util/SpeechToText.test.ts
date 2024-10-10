
import { multiLingualSpeechRecognizer } from "./SpeechToText";

global.fetch = jest.fn();
const createFetchResponse = (ok: boolean, data: any) => {
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

    (global.fetch as jest.Mock).mockResolvedValue(createFetchResponse(true, response));

    const recognizer = await multiLingualSpeechRecognizer();

    expect(recognizer.authorizationToken).toBe(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).toBe(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).toBe(languages.join(","));
  });

  it("creates a speech recognizer without configured languages if language config empty array", async () => {
    const token = "token";
    const region = "region";

    const response = {
      token: token,
      region: region,
      languages: [""]
    };

    (global.fetch as jest.Mock).mockResolvedValue(createFetchResponse(true, response));

    const recognizer = await multiLingualSpeechRecognizer();

    expect(recognizer.authorizationToken).toBe(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).toBe(region);
    // expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).toBe.undefined;
  });

  it("throws an error if speech config response not ok", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(createFetchResponse(false, {}));

    expect(async () => await multiLingualSpeechRecognizer()).rejects.toThrow("Network response was not ok");
  });

  it("throws an error if speech config fetching fails with an error", async () => {
    (global.fetch as jest.Mock).mockImplementationOnce(() => { throw new Error("Random error"); });
  });
});
