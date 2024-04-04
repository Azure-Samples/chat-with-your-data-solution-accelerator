import {
    SpeechConfig,
    AudioConfig,
    SpeechRecognizer,
    AutoDetectSourceLanguageConfig,
  } from "microsoft-cognitiveservices-speech-sdk";


export const multiLingualSpeechRecognizer = (
    subscriptionKey: string,
    serviceRegion: string,
    languages: string[]
  ) => {
        const speechConfig = SpeechConfig.fromSubscription(
          subscriptionKey,
          serviceRegion
        );
        const audioConfig = AudioConfig.fromDefaultMicrophoneInput();
        const autoDetectSourceLanguageConfig = AutoDetectSourceLanguageConfig.fromLanguages(languages)
        return SpeechRecognizer.FromConfig(speechConfig, autoDetectSourceLanguageConfig, audioConfig);
    };
