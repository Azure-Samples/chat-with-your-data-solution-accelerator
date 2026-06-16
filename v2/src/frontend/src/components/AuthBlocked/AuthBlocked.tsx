/**
 * Pillar: Stable Core
 * Phase: 5 (frontend — user identity)
 *
 * Full-view screen shown when the app runs with authentication enforced
 * but the Easy Auth `/.auth/me` lookup returned no signed-in user (the
 * `Blocked` auth phase). Adapted to Fluent v9 from the v1
 * "Authentication Not Configured" layout: a shield icon, a heading, and
 * operator guidance for wiring an identity provider. The shell renders
 * this in place of the routed view so the app makes no API call without
 * a resolvable user.
 */
import { Link, Text } from "@fluentui/react-components";
import { ShieldLockRegular } from "@fluentui/react-icons";
import { type JSX } from "react";
import styles from "./AuthBlocked.module.css";

const AZURE_PORTAL_URL = "https://portal.azure.com/";
const APP_SERVICE_AUTH_DOCS_URL =
  "https://learn.microsoft.com/azure/app-service/scenario-secure-app-authentication-app-service#3-configure-authentication-and-authorization";

export function AuthBlocked(): JSX.Element {
  return (
    <section
      className={styles.container}
      role="alert"
      data-testid="auth-blocked"
    >
      <ShieldLockRegular className={styles.icon ?? ""} aria-hidden="true" />
      <h1 className={styles.title}>Authentication Not Configured</h1>
      <Text as="p" className={styles.subtitle}>
        This app requires sign-in, but no signed-in user could be found. Add
        an identity provider by locating this app in the{" "}
        <Link href={AZURE_PORTAL_URL} target="_blank" rel="noreferrer">
          Azure Portal
        </Link>{" "}
        and following{" "}
        <Link href={APP_SERVICE_AUTH_DOCS_URL} target="_blank" rel="noreferrer">
          these instructions
        </Link>
        .
      </Text>
      <Text as="p" className={styles.note} weight="semibold">
        Authentication configuration takes a few minutes to apply. If you
        deployed in the last 10 minutes, please wait and reload the page.
      </Text>
    </section>
  );
}
