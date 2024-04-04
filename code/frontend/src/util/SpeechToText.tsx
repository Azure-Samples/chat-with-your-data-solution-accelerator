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
        var autoDetectSourceLanguageConfig = AutoDetectSourceLanguageConfig.fromLanguages(languages)
        const recognizer = SpeechRecognizer.FromConfig(speechConfig, autoDetectSourceLanguageConfig, audioConfig);
        return recognizer;
    };
