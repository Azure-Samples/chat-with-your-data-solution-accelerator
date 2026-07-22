/**
 * Shared chrome for the admin section. Renders a secondary navigation
 * bar -- a "back to chat home" button plus one <NavLink> per admin page
 * (Ingest data, Delete data, Configuration) -- above an
 * <Outlet/> for the active admin route. Mounted as the element of the
 * parent `/admin` route so every admin page shares the same nav frame
 * and the `/admin/<page>` deep links stay first-class.
 *
 * The back-home button routes to the chat root (`SectionPath[Chat]`).
 * Leaving the admin section unmounts the chat page, so returning lands
 * the operator on a fresh chat.
 */
import { type JSX } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Button } from "@fluentui/react-components";
import { Home20Regular } from "@fluentui/react-icons";
import { Section, SectionPath } from "@/models/sections";
import styles from "./AdminLayout.module.css";

interface AdminNavItem {
  section: Section;
  label: string;
  testId: string;
}

const ADMIN_NAV_ITEMS: readonly AdminNavItem[] = [
  {
    section: Section.AdminIngest,
    label: "Ingest data",
    testId: "admin-subnav-ingest",
  },
  {
    section: Section.AdminDelete,
    label: "Data set",
    testId: "admin-subnav-delete",
  },
  {
    section: Section.AdminConfig,
    label: "Configuration",
    testId: "admin-subnav-config",
  },
];

function navLinkClass({ isActive }: { isActive: boolean }): string | undefined {
  return isActive ? `${styles.link} ${styles.linkActive}` : styles.link;
}

export function AdminLayout(): JSX.Element {
  const navigate = useNavigate();
  return (
    <div className={styles.layout} data-testid="admin-layout">
      <div className={styles.bar}>
        <Button
          appearance="subtle"
          icon={<Home20Regular />}
          className={styles.backHome}
          data-testid="admin-back-home"
          onClick={() => {
            void navigate(SectionPath[Section.Chat]);
          }}
        >
          Back to CWYD
        </Button>
        <nav
          aria-label="Admin"
          className={styles.subnav}
          data-testid="admin-subnav"
        >
          {ADMIN_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.section}
              to={SectionPath[item.section]}
              className={navLinkClass}
              data-testid={item.testId}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className={styles.content}>
        <Outlet />
      </div>
    </div>
  );
}
