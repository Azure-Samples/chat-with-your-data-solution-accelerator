import {DefaultButton, IButtonProps } from "@fluentui/react";
import styles from "./HistoryButton.module.css";

interface ButtonProps extends IButtonProps {
  onClick: () => void;
  text: string | undefined;
}

export const HistoryButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.historyButtonRoot}
      text={text}
      iconProps={{ iconName: "History" }}
      onClick={onClick}
    />
  );
};
