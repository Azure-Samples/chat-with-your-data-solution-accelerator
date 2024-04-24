import { useEffect, useMemo, useState, MouseEvent } from "react";
import { Stack } from "@fluentui/react";
import { Tooltip } from "@fluentui/react-components";

import styles from "./Answer.module.css";

import { AskResponse, Citation } from "../../api";
import { parseAnswer } from "./AnswerParser";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import supersub from "remark-supersub";

import moment from "moment";

interface Props {
  answer: AskResponse;
  // onCitationClicked: (citedDocument: Citation, isKeyPressed: boolean) => void;
  onCitationClicked: (citedDocument: Citation) => void;
  // onCitationHover: (citedDocument: Citation) => void;
  index: number;
}

export const Answer = ({
  answer,
  onCitationClicked,
  // onCitationHover,
  index,
}: Props) => {
  const filePathTruncationLimit = 50;
  const messageBoxId = "message-" + index;
  const parsedAnswer = useMemo(() => parseAnswer(answer), [answer]);

  const [keyIsPressed, setKeyIsPressed] = useState(false);
  const [isCitationHovered, setIsCitationHovered] = useState(false);
  const [isCitationContentHovered, setIsCitationContentHovered] =
    useState(false);
  // const [hoveredCitation, setHoveredCitation] = useState<Citation>();

  /* useEffect(() => {
    setChevronIsExpanded(isRefAccordionOpen);
    // console.log('parsedAnswer: ', parsedAnswer);
  }, [isRefAccordionOpen]); */

  const createCitationFilepath = (
    citation: Citation,
    index: number,
    truncate: boolean = false
  ) => {
    let citationFilename = "";

    if (citation.filepath && citation.chunk_id != null) {
      if (truncate && citation.filepath.length > filePathTruncationLimit) {
        const citationLength = citation.filepath.length;
        citationFilename = `${citation.filepath.substring(0, 20)}...${citation.filepath.substring(citationLength - 20)} - Part ${parseInt(citation.chunk_id) + 1}`;
      } else {
        citationFilename = `${citation.filepath} - Part ${parseInt(citation.chunk_id) + 1}`;
      }
    } else {
      citationFilename = `Citation ${index}`;
    }
    return citationFilename;
  };

  const detectKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Shift" || e.key === "Control") {
      setKeyIsPressed(true);
      // console.log("Control clicked");

      /* if (isCitationHovered && hoveredCitation) {
        onCitationClicked(hoveredCitation);
      } */
    }
  };

  const detectKeyUp = (e: KeyboardEvent) => {
    /* if (e.key === "Shift" || e.key === "Control") {
      setKeyIsPressed(false);
      // console.log("Control un-clicked");
    } */
  };

  useEffect(() => {
    const handleCopy = () => {
      alert("Please consider where you paste this content.");
    };
    const messageBox = document.getElementById(messageBoxId);
    messageBox?.addEventListener("copy", handleCopy);
    // console.log('citations: ', parsedAnswer.citations);

    document.addEventListener("keydown", detectKeyDown, true);
    document.addEventListener("keyup", detectKeyUp, true);

    return () => {
      messageBox?.removeEventListener("copy", handleCopy);
      document.removeEventListener("keydown", detectKeyDown, true);
      document.removeEventListener("keyup", detectKeyUp, true);
    };
  }, []);

  return (
    <>
      {parsedAnswer.citations.length > 0 && (
        <Stack className={`${styles.answerContainer}`} id={messageBoxId}>
          <Stack
            horizontal
            className={` ${styles.answerFooter} `}
            verticalAlign="start"
          >
            <span className={styles.sourcesTitle}>Sources</span>

            <div
              style={{
                marginTop: 8,
                display: "flex",
                flexDirection: "column",
                height: "100%",
                gap: "4px",
                maxWidth: "100%",
              }}
            >
              {parsedAnswer.citations.map((citation, idx) => {
                return (
                  <Tooltip
                    onVisibleChange={(e) => {
                      // console.log('changed: ', e);
                      if (e?.type === "pointerleave") {
                        setKeyIsPressed(false);
                      }
                    }}
                    content={{
                      children:
                        keyIsPressed || isCitationContentHovered ? (
                          // ↓ this is where you form the tooltip content
                          <div className={`${styles.citationToolTipInner}`}>
                            <ReactMarkdown
                              className={`${styles.citationPanelContent} ${styles.mobileCitationPanelContent}`}
                              children={citation.content}
                              remarkPlugins={[remarkGfm]}
                              rehypePlugins={[rehypeRaw]}
                            />
                          </div>
                        ) : null,
                      className:
                        keyIsPressed || isCitationContentHovered
                          ? styles.citationToolTip
                          : styles.hide,
                    }}
                    key={idx}
                    relationship="label"
                    positioning={"after-bottom"}
                    withArrow
                  >
                    <span
                      onClick={() => onCitationClicked(citation)}
                      // onClick={() => onCitationClicked(citation, keyIsPressed)}
                      className={styles.citationContainer}
                    >
                      <div className={styles.citation}>{idx + 1}</div>

                      {/* ↓ this is the original Citation title generator */}
                      {/* {createCitationFilepath(citation, idx, true)} */}

                      {/* ↓ testing getting other title/source info */}
                      <div className={styles.citationTitle}>
                        {citation.metadata?.title || "Citation"}
                      </div>
                      <div className={styles.citationSource}>
                        •&nbsp;&nbsp;{citation.metadata?.source || "Source"}
                      </div>
                    </span>
                  </Tooltip>
                );
              })}
            </div>
          </Stack>
        </Stack>
      )}

      <div
        className={`${styles.answerContainer} ${styles.answerProntoResponse}`}
      >
        <Stack.Item grow>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, supersub]}
            children={parsedAnswer.markdownFormatText}
            className={styles.answerText}
          />
        </Stack.Item>
      </div>

      {parsedAnswer.citations.length > 0 && (
        <div className={` ${styles.answerNewFooter}`}>
          {/* ↓ TEMP - this will need to be timestamp from BE */}
          <div>{moment().calendar()}</div>
          {/* <div>{moment().format("dddd [at] HH:mm")}</div> */}
          <div>•</div>
          <div>AI-generated content may be incorrect</div>
        </div>
      )}
    </>
  );
};
