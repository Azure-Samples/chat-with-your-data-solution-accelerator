import {
    SpeechConfig,
    AudioConfig,
    SpeechRecognizer,
    AutoDetectSourceLanguageConfig,
  } from "microsoft-cognitiveservices-speech-sdk";


export const multiLingualSpeechRecognizer = (
    token: string,
    serviceRegion: string,
    languages: string[]
  ) => {
        const speechConfig = SpeechConfig.fromAuthorizationToken(
          token,
          serviceRegion
        );
        const audioConfig = AudioConfig.fromDefaultMicrophoneInput();
        const autoDetectSourceLanguageConfig = AutoDetectSourceLanguageConfig.fromLanguages(languages)
        return SpeechRecognizer.FromConfig(speechConfig, autoDetectSourceLanguageConfig, audioConfig);
    };
