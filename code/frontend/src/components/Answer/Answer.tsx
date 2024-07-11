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
declare global {
    interface Window {
      webkitAudioContext: typeof AudioContext;
    }
  }
interface Props {
    answer: AskResponse;
    onCitationClicked: (citedDocument: Citation) => void;
    index: number;
}
const MyStackComponent = forwardRef<HTMLDivElement, any>((props, ref) => (
    <div {...props} ref={ref} />
  ));

export const Answer = ({
    answer,
    onCitationClicked,
    index,
}: Props) => {
    const [isRefAccordionOpen, { toggle: toggleIsRefAccordionOpen }] = useBoolean(false);
    const filePathTruncationLimit = 50;
    const answerContainerRef =  useRef<HTMLDivElement>(null);// read the text from the container
    const messageBoxId = "message-" + index;
    const [isSpeaking, setIsSpeaking] = useState(false); // for speaker on
    const [showSpeaker, setShowSpeaker] = useState(true); //for show and hide the speaker icon
    const [isPaused, setIsPaused] = useState(false); //for pause
    const parsedAnswer = useMemo(() => parseAnswer(answer), [answer]);
    const [chevronIsExpanded, setChevronIsExpanded] = useState(isRefAccordionOpen);
    const refContainer = useRef<HTMLDivElement>(null);
    const [audioContext, setAudioContext] = useState<AudioContext | null>(null); //Manully  manage the audio context eg pausing resuming
    // const [synthesizer, setSynthesizer] = useState<sdk.SpeechSynthesizer | null>(null);
    const handleChevronClick = () => {
        setChevronIsExpanded(!chevronIsExpanded);
        toggleIsRefAccordionOpen();
      };

    const fetchSpeechConfig = async (): Promise<{ key: string; region: string }> => {
        const response = await fetch('/api/speech');
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        return { key: data.key, region: data.region };
    };

    const initializeSynthesizer = async () => {
        const { key, region } = await fetchSpeechConfig();
        const speechConfig = sdk.SpeechConfig.fromSubscription(key, region);
        const audioConfig = sdk.AudioConfig.fromDefaultSpeakerOutput();
        const synthesizer = new sdk.SpeechSynthesizer(speechConfig, audioConfig);

        return synthesizer;
      };

    useEffect(() => {
        setChevronIsExpanded(isRefAccordionOpen);
        if(chevronIsExpanded && refContainer.current){
            refContainer.current.scrollIntoView({ behavior:'smooth'});
        }
        // After genrating answer then only show speaker icon
        if (parsedAnswer.markdownFormatText === "Generating answer...") {
            setShowSpeaker(false);
          } else {
            setShowSpeaker(true);
          }
    }, [chevronIsExpanded,isRefAccordionOpen, parsedAnswer]);

    const createCitationFilepath = (citation: Citation, index: number, truncate: boolean = false) => {
        let citationFilename = "";

        if (citation.filepath && citation.chunk_id != null) {
            if (truncate && citation.filepath.length > filePathTruncationLimit) {
                const citationLength = citation.filepath.length;
                citationFilename = `${citation.filepath.substring(0, 20)}...${citation.filepath.substring(citationLength -20)} - Part ${citation.chunk_id}`;
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
        // Get the answer
        if (answerContainerRef.current) {
          const text = answerContainerRef.current.textContent ?? '';
          return text;
        }
        return '';
      };

      const handleSpeak = async () => {
        try {
          const text = getAnswerText();
          console.log('text:::', text);
          setIsSpeaking(true);
          const synth = await initializeSynthesizer();
        //   setSynthesizer(synth);
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          const context = new AudioContext();
          setAudioContext(context);
          synth.speakTextAsync(
            text,
            result => {
                if (result.reason === sdk.ResultReason.SynthesizingAudioCompleted) {
                    console.log('Synthesis completed');
                    setIsSpeaking(false);
                    setIsPaused(false);
                    context.close();
                  }
                //   if (result.reason === sdk.ResultReason.SynthesizingAudioStarted) {
                //     console.log('Synthesis started');
                //     setIsSpeaking(false);
                //     setIsPaused(true);
                //   }

            },
            error => {
              console.error('Synthesis error:', error);
              setIsSpeaking(false);
              setIsPaused(false);
              context.close();
            }
          );
        } catch (error) {
          console.error('Error:', error);
          setIsSpeaking(false);
          setIsPaused(false);
        }
      };

      const handlePause = async () => {
        if (audioContext) {
          if (isPaused) {
            audioContext.resume().then(() => {
              console.log('Resumed');
              setIsPaused(false);
            }).catch(error => {
              console.error('Resume error:', error);
            });
          } else {
            audioContext.suspend().then(() => {
              console.log('Paused');
              setIsPaused(true);
            }).catch(error => {
              console.error('Pause error:', error);
            });
          }
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
                        <Stack style={{width: "100%"}} >
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
                   {showSpeaker && (
                        <button id="speakerbtn" onClick={handleSpeak} style={{ border: 0, backgroundColor: 'transparent', display: isSpeaking? "none" : "block" }}>
                        <img src={speakerIcon} alt="Speak" />
                        </button>
                    )}
                    {isSpeaking && (
                        <button id="pausebtn" onClick={handlePause} style={{ border: 0, backgroundColor: 'transparent' , display: !isSpeaking? "none" : "block" }} >
                        <img src={pauseIcon} alt={isPaused ? 'Resume' : 'Pause'} />
                        </button>
                    )}
                </Stack.Item>
            </MyStackComponent>
        </>
    );
};
