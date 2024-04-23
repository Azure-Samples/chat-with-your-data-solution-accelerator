import * as React from "react";
import {
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  InlineDrawer,
  Button,
  Menu,
  MenuTrigger,
  MenuPopover,
} from "@fluentui/react-components";
import {
  Dismiss24Regular,
  TextBulletListSquareFilled,
} from "@fluentui/react-icons";
import styles from "./Sidebar.module.css";

export const Sidebar = () => {
  const [isOpen, setIsOpen] = React.useState(true);

  return (
    <div className={styles.sidebar}>
      <InlineDrawer
        open={isOpen}
        // onOpenChange={(_, { open }) => setIsOpen(open)}
        style={{
          width: "auto",
          borderRight: "1px solid #D4D4D4",
          boxShadow: "0px 1px 4px 0px #0000003D",
        }}
      >
        <div className={styles.sidebarMain}>
          <div className={styles.sidebarHeader}>
            <div className={styles.newThreadActions}>
              <div className={styles.newThreadBtn}>
                <img src="../../plusIcon.png" />
                <span>New Thread</span>
              </div>
              <div className={styles.newThreadHotkeyIcons}>
                <img src="../../Cntrl_key_icon.png" />
                <img src="../../K_key_icon.png" />
              </div>
            </div>

            <div
              className={`${styles.closeSideBarBtn} ghostIconBtn`}
              onClick={() => setIsOpen(false)}
            >
              <img src="../../dock_to_right.png" alt="close side bar button" />
            </div>
          </div>

          <div className={styles.sidebarBody}>
            <span className={styles.threadsHeader}>Threads</span>
            <ul className={`menuListContainer`}>
              {/* ↓ should be in for loop when data is hooked up */}
              <li
                className={`${styles.threadMenuItem} menuListItem activeListItem`}
              >
                <div className={`listItemLabel`}>
                  <img src="../../threadIcon.png" />
                  <span>Example Test Thread</span>
                </div>
                <Menu>
                  <MenuTrigger disableButtonEnhancement>
                    <div className={`${styles.threadMenu} ghostIconBtn`}>
                      <img src="../../ellipsesIconBlue.png" />
                    </div>
                  </MenuTrigger>

                  <MenuPopover style={{ padding: "0px" }}>
                    <ul className={`${styles.headerMenu} menuListContainer`}>
                      <li className={`menuListItem disabled`}>
                        <div className={`listItemLabel`}>
                          <img src="../../shareLinkIcon_blue.png" />
                          <span>Share Thread</span>
                        </div>
                      </li>
                      <li className={`menuListItem disabled`}>
                        <div className={`listItemLabel`}>
                          <img src="../../editIcon.png" />
                          <span>Rename</span>
                        </div>
                      </li>
                      <li className={`menuListItem disabled`}>
                        <div className={`listItemLabel`}>
                          <img src="../../deleteIcon.png" />
                          <span>Delete Thread</span>
                        </div>
                      </li>
                    </ul>
                  </MenuPopover>
                </Menu>
              </li>
            </ul>
          </div>
        </div>
      </InlineDrawer>

      <div
        className={`${styles.openSideMenuBtn} ghostIconBtn`}
        onClick={() => setIsOpen(true)}
      >
        <img src="../../dock_to_right_outline.png" />
      </div>
    </div>
  );
};
