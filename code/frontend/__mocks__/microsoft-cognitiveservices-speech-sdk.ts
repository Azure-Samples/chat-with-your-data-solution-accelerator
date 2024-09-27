export class SpeechRecognizer {
    recognizeOnceAsync(callback: (result: { reason: string; text: string }) => void) {
      callback({
        reason: ResultReason.RecognizedSpeech,
        text: 'mocked speech result',
      });
    }
  }

  export enum ResultReason {
    RecognizedSpeech = 'RecognizedSpeech',
    NoMatch = 'NoMatch',
  }

  // You can also mock other classes or methods from the SDK if needed, e.g. SpeechConfig, AudioConfig
  export class SpeechConfig {
    static fromSubscription(key: string, region: string) {
      return new SpeechConfig();
    }
  }

  export class AudioConfig {
    static fromDefaultMicrophoneInput() {
      return new AudioConfig();
    }
  }
