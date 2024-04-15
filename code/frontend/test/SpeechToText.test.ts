import { expect } from "chai";
import { it } from "mocha";
import { multiLingualSpeechRecognizer } from "../src/util/SpeechToText.js";

describe("SpeechToText", () => {
  it("creates a speech recognizer with multiple languages", async () => {
    const token = "token";
    const region = "region";
    const languages = ["en-US", "fr-FR", "de-DE", "it-IT"];
    const recognizer = multiLingualSpeechRecognizer(token, region, languages);

    expect(recognizer.authorizationToken).to.equal(token);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_Region")).to.equal(region);
    expect(recognizer.properties.getProperty("SpeechServiceConnection_AutoDetectSourceLanguages")).to.equal(languages.join(","));
  });
});
