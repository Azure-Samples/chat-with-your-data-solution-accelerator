import {
    SpeechConfig,
    AudioConfig,
    SpeechRecognizer,
    AutoDetectSourceLanguageConfig,
  } from "microsoft-cognitiveservices-speech-sdk";

const fetchSpeechConfig = async (): Promise<{ token: string, region: string, languages: string[]; }> => {
  try {
    const response = await fetch("/api/speech");

    if (!response.ok) {
      console.error("Error fetching speech config:", response);
      throw new Error("Network response was not ok");
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching server configuration:", error);
    throw error;
  }
};

export const multiLingualSpeechRecognizer = async () => {
        const { token, region, languages } = await fetchSpeechConfig();

        const speechConfig = SpeechConfig.fromAuthorizationToken(
          token,
          region
        );

        const audioConfig = AudioConfig.fromDefaultMicrophoneInput();

        try {
          const autoDetectSourceLanguageConfig = AutoDetectSourceLanguageConfig.fromLanguages(languages);
          return SpeechRecognizer.FromConfig(speechConfig, autoDetectSourceLanguageConfig, audioConfig);
        } catch (error) {
          console.error("Using default language settings as error detected while reading language config:", error);
          return new SpeechRecognizer(speechConfig, audioConfig);
        }
    };
