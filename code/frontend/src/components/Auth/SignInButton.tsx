import { useMsal } from "@azure/msal-react";
import styles from "./Auth.module.css";

export const SignInButton = () => {
  const { instance } = useMsal();

  return (
    <div
      className={styles.buttonContainer}
      role="button"
      tabIndex={0}
      aria-label="Sign In"
      onClick={() => instance.loginPopup()}
      onKeyDown={e => e.key === "Enter" || e.key === " " ? instance.loginPopup() : null}
    >
      Sign In
    </div>
  );
}
