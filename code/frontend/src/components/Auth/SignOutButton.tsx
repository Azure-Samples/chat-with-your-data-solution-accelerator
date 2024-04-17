import { useMsal } from "@azure/msal-react";
import styles from "./Auth.module.css";

export const SignOutButton = () => {
  const { instance, accounts } = useMsal();

  const logoutRequest = {
    account: instance.getAccountByHomeId(accounts[0].homeAccountId),
    mainWindowRedirectUri: "/",
    postLogoutRedirectUri: "/",
  };

  return (
    <div
      className={`${styles.buttonContainer} ${styles.signOutButton}`}
      role="button"
      tabIndex={0}
      aria-label="Sign Out"
      onClick={() => instance.logoutPopup(logoutRequest)}
      onKeyDown={e => e.key === "Enter" || e.key === " " ? instance.loginPopup() : null}
    >
      Sign Out
    </div>
  );
}
