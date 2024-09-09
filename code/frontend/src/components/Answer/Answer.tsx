import { useEffect, useMemo, useState, useRef, forwardRef } from "react";
import { useBoolean } from "@fluentui/react-hooks"
import { FontIcon, Stack, Text } from "@fluentui/react";
import styles from "./Answer.module.css";
import { AskResponse, Citation } from "../../api";
import { parseAnswer } from "./AnswerParser";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from 'remark-supersub'
import pauseIcon from "../../assets/pauseIcon.svg";
import speakerIcon from "../../assets/speakerIcon.svg";
import * as sdk from 'microsoft-cognitiveservices-speech-sdk';

import * as SpeechSDK from 'microsoft-cognitiveservices-speech-sdk';

declare global {
  interface Window {
    webkitAudioContext: typeof AudioContext;
  }
}
interface Props {
  answer: AskResponse;
  onCitationClicked: (citedDocument: Citation) => void;
  onSpeak?: any;
  isActive?: boolean;
  index: number;
}
const MyStackComponent = forwardRef<HTMLDivElement, any>((props, ref) => (
  <div {...props} ref={ref} />
));

export const Answer = ({
  answer,
  onCitationClicked,
  onSpeak,
  isActive,
  index,
}: Props) => {
  const [isRefAccordionOpen, { toggle: toggleIsRefAccordionOpen }] = useBoolean(false);
  const filePathTruncationLimit = 50;
  const answerContainerRef = useRef<HTMLDivElement>(null);// read the text from the container
  const messageBoxId = "message-" + index;
  const [isSpeaking, setIsSpeaking] = useState(false); // for speaker on
  const [showSpeaker, setShowSpeaker] = useState(true); //for show and hide the speaker icon
  const [isPaused, setIsPaused] = useState(false); //for pause
  const parsedAnswer = useMemo(() => parseAnswer(answer), [answer]);
  const [chevronIsExpanded, setChevronIsExpanded] = useState(isRefAccordionOpen);
  const refContainer = useRef<HTMLDivElement>(null);
  const [audioContext, setAudioContext] = useState<AudioContext | null>(null); //Manully  manage the audio context eg pausing resuming


  const [synthesizerData, setSynthesizerData] = useState({ key: '', region: '' });
  const [synthesizer, setSynthesizer] = useState<SpeechSDK.SpeechSynthesizer | null>(null);
  const [audioDestination, setAudioDestination] = useState<SpeechSDK.SpeakerAudioDestination | null>(null);
  const [playbackTimeout, setPlaybackTimeout] = useState<NodeJS.Timeout | null>(null);
  const [remainingDuration, setRemainingDuration] = useState<number>(0);
  const [startTime, setStartTime] = useState<number | null>(null);

  const handleChevronClick = () => {
    setChevronIsExpanded(!chevronIsExpanded);
    toggleIsRefAccordionOpen();
  };

  const initializeSynthesizer = () => {
    const speechConfig = sdk.SpeechConfig.fromSubscription(synthesizerData.key, synthesizerData.region);
    const newAudioDestination = new SpeechSDK.SpeakerAudioDestination();
    const audioConfig = SpeechSDK.AudioConfig.fromSpeakerOutput(newAudioDestination);
    const newSynthesizer = new SpeechSDK.SpeechSynthesizer(speechConfig, audioConfig);
    setSynthesizer(newSynthesizer);
    setAudioDestination(newAudioDestination);
    if (playbackTimeout) {
      clearTimeout(playbackTimeout);
    }
    setRemainingDuration(0);
  }

  useEffect(() => {
    if (synthesizerData.key != '') {
      initializeSynthesizer();

      return () => {
        if (synthesizer) {
          synthesizer.close();
        }
        if (audioDestination) {
          audioDestination.close();
        }
        if (playbackTimeout) {
          clearTimeout(playbackTimeout);
        }
      };
    }

  }, [index, synthesizerData]);

  useEffect(() => {
    const fetchSythesizerData = async () => {
      const response = await fetch('/api/speech');
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      const data = await response.json();
      setSynthesizerData({ key: data.key, region: data.region });
    }
    fetchSythesizerData();
  }, [])

  useEffect(() => {
    if (!isActive && synthesizer && isSpeaking) {
      resetSpeech()
    }
  }, [isActive, synthesizer]);

  useEffect(() => {
    setChevronIsExpanded(isRefAccordionOpen);
    if (chevronIsExpanded && refContainer.current) {
      refContainer.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chevronIsExpanded, isRefAccordionOpen])

  useEffect(() => {
    // After genrating answer then only show speaker icon
    if (parsedAnswer.markdownFormatText === "Generating answer...") {
      setShowSpeaker(false);
    } else {
      setShowSpeaker(true);
    }
  }, [parsedAnswer]);

  const createCitationFilepath = (citation: Citation, index: number, truncate: boolean = false) => {
    let citationFilename = "";

    if (citation.filepath && citation.chunk_id != null) {
      if (truncate && citation.filepath.length > filePathTruncationLimit) {
        const citationLength = citation.filepath.length;
        citationFilename = `${citation.filepath.substring(0, 20)}...${citation.filepath.substring(citationLength - 20)} - Part ${citation.chunk_id}`;
      }
      else {
        citationFilename = `${citation.filepath} - Part ${citation.chunk_id}`;
      }
    }
    else {
      citationFilename = `Citation ${index}`;
    }
    return citationFilename;
  }

  const getAnswerText = () => {
    if (answerContainerRef.current) {
      const text = answerContainerRef.current.textContent ?? '';
      return text;
    }
    return '';
  };

  const startSpeech = () => {
    if (synthesizer) {
      const text = getAnswerText();
      synthesizer?.speakTextAsync(
        text,
        result => {
          if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
            const duration = result.audioDuration / 10000;
            setRemainingDuration(duration);
            setStartTime(Date.now());
            handleTimeout(duration);
          } else if (result.reason === SpeechSDK.ResultReason.Canceled) {
            setIsSpeaking(false);
            setIsPaused(false);
          } else {
            console.error('Synthesis failed: ', result.errorDetails);
          }
        },
        error => {
          console.error('Synthesis error: ', error);
          setIsSpeaking(false);
          setIsPaused(false);
        }
      );
      setIsSpeaking(true);
    }
  };

  const handleTimeout = (remainingDuration: number) => {
    setPlaybackTimeout(
      setTimeout(() => {
        setIsSpeaking(false);
        setIsPaused(false);
        onSpeak(index, 'stop');
      }, remainingDuration)
    );
  };

  const resetSpeech = () => {
    //audioDestination?.close();
    audioDestination?.pause();
    setIsSpeaking(false);
    setIsPaused(false);
    //synthesizer?.close();
    initializeSynthesizer();
  }
  const handleSpeakPauseResume = () => {
    if (isSpeaking) {
      if (isPaused) {
        onSpeak(index, 'speak');
        audioDestination?.resume();
        setIsPaused(false);
        setStartTime(Date.now());
        handleTimeout(remainingDuration);
      } else {
        onSpeak(index, 'pause');
        audioDestination?.pause();
        setIsPaused(true);
        const elapsed = Date.now() - (startTime || 0);
        const newRemainingDuration = remainingDuration - elapsed;
        setRemainingDuration(newRemainingDuration);
        if (playbackTimeout) {
          clearTimeout(playbackTimeout);
        }
      }
    } else {
      onSpeak(index, 'speak');
      startSpeech();
    }
  };

  useEffect(() => {
    const handleCopy = () => {
      alert("Please consider where you paste this content.");
    };
    const messageBox = document.getElementById(messageBoxId);
    messageBox?.addEventListener("copy", handleCopy);
    return () => {
      messageBox?.removeEventListener("copy", handleCopy);
    };
  }, []);

  const getSpeechButtons = () => {
    const speechStatus = !showSpeaker ? "none" : showSpeaker && !isSpeaking ? "Speak"
      : isSpeaking && isPaused ? "Resume" : "Pause";

    switch (speechStatus) {
      case 'Speak':
      case 'Resume':
        return (
          <button id="speakerbtn" title={"Read aloud"} onClick={handleSpeakPauseResume} style={{ border: 0, backgroundColor: 'transparent' }}>
            <img src={speakerIcon} alt="Speak" />
          </button>
        )
      case 'Pause':
        return (
          <button id="pausebtn" title={"Pause"} onClick={handleSpeakPauseResume} style={{ border: 0, backgroundColor: 'transparent' }} >
            <img src={pauseIcon} alt={isPaused ? 'Resume' : 'Pause'} />
          </button>
        )
      default:
        return null;
    }
  }

  return (
    <>
      <MyStackComponent className={styles.answerContainer} id={messageBoxId} ref={answerContainerRef}>
        <Stack.Item grow>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, supersub]}
            children={parsedAnswer.markdownFormatText}
            className={styles.answerText}
          />
        </Stack.Item>
        <Stack horizontal className={styles.answerFooter} verticalAlign="start">
          <Stack.Item className={styles.answerDisclaimerContainer}>
            <span className={`${styles.answerDisclaimer} ${styles.mobileAnswerDisclaimer}`}>AI-generated content may be incorrect</span>
          </Stack.Item>

          {!!parsedAnswer.citations.length && (
            <Stack.Item aria-label="References">
              <Stack style={{ width: "100%" }} >
                <Stack horizontal horizontalAlign='start' verticalAlign='center'>
                  <Text
                    className={styles.accordionTitle}
                    onClick={toggleIsRefAccordionOpen}
                  >
                    <span>{parsedAnswer.citations.length > 1 ? parsedAnswer.citations.length + " references" : "1 reference"}</span>
                  </Text>
                  <FontIcon className={styles.accordionIcon}
                    onClick={handleChevronClick} iconName={chevronIsExpanded ? 'ChevronDown' : 'ChevronRight'}
                  />
                </Stack>

              </Stack>
            </Stack.Item>
          )}

        </Stack>
        {chevronIsExpanded &&
          <div ref={refContainer} style={{ marginTop: 8, display: "flex", flexDirection: "column", height: "100%", gap: "4px", maxWidth: "100%" }}>
            {parsedAnswer.citations.map((citation, idx) => {
              return (
                <span title={createCitationFilepath(citation, ++idx)} key={idx} onClick={() => onCitationClicked(citation)} className={styles.citationContainer}>
                  <div className={styles.citation} key={idx}>{idx}</div>
                  {createCitationFilepath(citation, idx, true)}
                </span>);
            })}
          </div>
        }
        <Stack.Item>
          {getSpeechButtons()}
        </Stack.Item>
      </MyStackComponent>
    </>
  );
};
