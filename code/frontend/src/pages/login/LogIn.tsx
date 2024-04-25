import { useRef, useState, useEffect } from "react";
import { Stack } from "@fluentui/react";

import styles from "./LogIn.module.css";
import { Input, Label, useId } from "@fluentui/react-components";
import type { InputProps } from "@fluentui/react-components";
import { ArrowEnterFilled } from "@fluentui/react-icons";

const LogIn = (props: InputProps) => {
  const inputId = useId("input");
  const [liveRecognizedText, setLiveRecognizedText] = useState<string>("");

  const submitLogInField = (passwordEntered: string) => {
    if (passwordEntered.trim() === "nagenai") {
      console.log("yup, passed");
    } else {
      console.log("nope, wrong");
    }
  };

  useEffect(() => {});

  return (
    <div className={styles.container}>
      <img
        className={styles.prontoAvatar}
        src="../../pronto-avatar-anim-white-bg.gif"
        alt="pronto avatar animated"
      />
      <div className={styles.logInHolder}>
        <div className={styles.logInInner}>
          <Label htmlFor={inputId}>Welcome to Pronto, please log in!</Label>
          <Input
            id={inputId}
            {...props}
            placeholder={"Enter Password"}
            contentAfter={
              <ArrowEnterFilled
                aria-label="Enter with password"
                onClick={(e) => submitLogInField(liveRecognizedText)}
              />
            }
            onChange={(e, newValue) => {
              if (newValue !== undefined) {
                setLiveRecognizedText(newValue.value);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                submitLogInField(liveRecognizedText);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default LogIn;
