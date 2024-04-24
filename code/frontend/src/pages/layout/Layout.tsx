import { Outlet } from "react-router-dom";
import styles from "./Layout.module.css";
import { Header } from "../../components/Header";

const Layout = () => {
  return (
    <div className={styles.layout}>
      <Header></Header>

      {/* ↓ page content */}
      <Outlet />
    </div>
  );
};

export default Layout;
