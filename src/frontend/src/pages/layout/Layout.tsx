import { Outlet } from "react-router-dom";
import styles from "./Layout.module.css";

const Layout = () => {
    return (
        <div className={styles.layout}>
            <header className={styles.header}>
                <h1 className={styles.headerTitle}>Chat with Your Data</h1>
            </header>
            <main className={styles.main}>
                <Outlet />
            </main>
        </div>
    );
};

export default Layout;
