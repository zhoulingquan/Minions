import { Layout, Space } from "antd";
import ThemeToggleButton from "../components/ThemeToggleButton";
import styles from "./index.module.less";

const { Header: AntHeader } = Layout;

export default function Header() {
  return (
    <AntHeader className={styles.header}>
      <Space size="middle" className={styles.headerRight}>
        <ThemeToggleButton />
      </Space>
    </AntHeader>
  );
}
