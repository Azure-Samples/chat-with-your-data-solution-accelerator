import {
    SpeechConfig,
    AudioConfig,
    SpeechRecognizer,
    AutoDetectSourceLanguageConfig,
  } from "microsoft-cognitiveservices-speech-sdk";


export const multiLingualSpeechRecognizer = (
    token: string,
    serviceRegion: string
  ) => {
        const speechConfig = SpeechConfig.fromAuthorizationToken(
          token,
          serviceRegion
        );
        const languagesToRecognize = import.meta.env.VITE_SPEECH_RECOGNIZER_LANGUAGES
        ? import.meta.env.VITE_SPEECH_RECOGNIZER_LANGUAGES.split(",")
        : "en-US";

        console.log('languagesToRecognize', languagesToRecognize);

        const audioConfig = AudioConfig.fromDefaultMicrophoneInput();
        const autoDetectSourceLanguageConfig = AutoDetectSourceLanguageConfig.fromLanguages(languagesToRecognize)
        return SpeechRecognizer.FromConfig(speechConfig, autoDetectSourceLanguageConfig, audioConfig);
    };
