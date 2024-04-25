import { Link } from "react-router-dom";
import styles from "./Header.module.css";
import { Stack } from "@fluentui/react";
import {
  Tooltip,
  Button,
  Menu,
  MenuTrigger,
  MenuList,
  MenuItem,
  MenuPopover,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import {
  DoorArrowLeftFilled,
  PersonSettingsFilled,
} from "@fluentui/react-icons";

export const Header = () => {
  const [copyClicked, setCopyClicked] = useState<boolean>(false);

  const handleCopyClick = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopyClicked(true);
  };

  const resetCopyClick = () => {
    setTimeout(() => {
      setCopyClicked(false);
    }, 500);
  };

  /* useEffect(() => {

    },); */

  return (
    <header className={styles.header} role={"banner"}>
      <div className={styles.headerContainer}>
        <Stack horizontal verticalAlign="center">
          <Link to="/" className={styles.headerTitleContainer}>
            <img
              src="../../src/assets/logo.svg"
              className={styles.headerIcon}
              aria-hidden="true"
            />
            <h3 className={styles.headerTitle}>Pronto</h3>
          </Link>

          <div className={styles.mainNavLinks}>
            <Tooltip
              content={{
                children: (
                  // ↓ this is where you form the tooltip content
                  <div className={styles.dataSourceToolTipInner}>
                    <img
                      src="../../addSourceTooltipIcon.png"
                      // className={styles.addSourceButton}
                      aria-hidden="true"
                    />
                    <span>Add a data source</span>
                  </div>
                ),
                className: styles.dataSourceToolTip,
              }}
              relationship="label"
              positioning={"below"}
            >
              {/* ↓ this is where the hoverable content goes */}
              <div className={styles.addSourceButtonContainer}>
                <a
                  href="https://web-5cmvhl67t5ruq-admin.azurewebsites.net/Ingest_Data"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img
                    src="../../addSourceIcon.png"
                    className={styles.addSourceButton}
                    aria-hidden="true"
                  />
                </a>
              </div>
            </Tooltip>

            <Tooltip
              content={{
                children: (
                  // ↓ this is where you form the tooltip content
                  <div className={styles.shareToolTipInner}>
                    {!copyClicked ? (
                      <span>Share Pronto</span>
                    ) : (
                      <div className={styles.copiedToClipboard}>
                        <img
                          src="../../copiedIcon.png"
                          alt="Pronto link copied to clipbaord"
                        />
                        <span>Link copied to clipboard!</span>
                      </div>
                    )}
                  </div>
                ),
                className: styles.shareToolTip,
              }}
              relationship="label"
              positioning={"below"}
            >
              {/* ↓ this is where the hoverable content goes */}
              <div
                className={styles.shareButtonContainer}
                role="button"
                tabIndex={0}
                aria-label="Share"
                onClick={handleCopyClick}
                onKeyDown={(e) =>
                  e.key === "Enter" || e.key === " " ? handleCopyClick() : null
                }
                onMouseLeave={(e) => resetCopyClick()}
              >
                <img
                  src="../../shareLinkIcon.png"
                  className={styles.shareButton}
                  aria-hidden="true"
                />
              </div>
            </Tooltip>

            <Menu>
              <MenuTrigger disableButtonEnhancement>
                <div className={styles.userMenuBtn}>
                  <span>Eddie Hoover</span>
                  <img
                    className={styles.userMenuArrows}
                    src="../../menuExpandIcon.png"
                  />
                </div>
              </MenuTrigger>

              <MenuPopover style={{ padding: "0px" }}>
                <ul className={`${styles.headerMenu} menuListContainer`}>
                  <li className={`menuListItem disabled`}>
                    <div className={`listItemLabel`}>
                      <PersonSettingsFilled />
                      <span>Settings</span>
                    </div>
                  </li>
                  <li className={`menuListItem disabled`}>
                    <div className={`listItemLabel`}>
                      <DoorArrowLeftFilled />
                      <span>Log Out</span>
                    </div>
                  </li>
                </ul>
              </MenuPopover>
            </Menu>
          </div>
        </Stack>
      </div>
    </header>
  );
};
