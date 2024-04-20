import * as React from "react";
import {
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  InlineDrawer,
  Button,
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
        style={{ width: "auto" }}
      >
        <div className={styles.sidebarMain}>
          {/* <DrawerHeader>
            <DrawerHeaderTitle
              action={
                <Button
                  appearance="subtle"
                  aria-label="Close"
                  icon={<Dismiss24Regular />}
                  onClick={() => setIsOpen(false)}
                />
              }
            >
              Overlay Drawer
            </DrawerHeaderTitle>
          </DrawerHeader>

          <DrawerBody>
            <p>Drawer content</p>
          </DrawerBody> */}

          <div className={styles.sidebarHeader}>
            <div className={styles.newThreadActions}></div>

            <div
              className={styles.closeSideBarBtn}
              onClick={() => setIsOpen(false)}
            >
              <img src="../../dock_to_right.png" alt="close side bar button" />
            </div>
          </div>

          <div className={styles.sidebarBody}>
            <span>Threads</span>
            <ul>
              <li>
                {/* icon */}
                <span>Example Test Thread</span>
              </li>
            </ul>
          </div>
        </div>
      </InlineDrawer>

      <TextBulletListSquareFilled
        className={styles.openSideMenuBtn}
        onClick={() => setIsOpen(true)}
      />
    </div>
  );
};
