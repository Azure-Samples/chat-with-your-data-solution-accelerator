import { Outlet, NavLink } from "react-router-dom";
import styles from "./App.module.css";

const navItems = [
    { to: "/ingest", label: "Ingest Data" },
    { to: "/explore", label: "Explore Data" },
    { to: "/delete", label: "Delete Data" },
    { to: "/config", label: "Configuration" },
];

const App = () => {
    return (
        <div className={styles.layout}>
            <nav className={styles.sidebar}>
                <h2 className={styles.sidebarTitle}>CWYD Admin</h2>
                <ul className={styles.navList}>
                    {navItems.map((item) => (
                        <li key={item.to}>
                            <NavLink
                                to={item.to}
                                className={({ isActive }) =>
                                    isActive ? styles.navLinkActive : styles.navLink
                                }
                            >
                                {item.label}
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>
            <main className={styles.content}>
                <Outlet />
            </main>
        </div>
    );
};

export default App;
