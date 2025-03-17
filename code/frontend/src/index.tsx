// App.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route } from "react-router-dom";
import { initializeIcons } from "@fluentui/react";

import "./index.css";

import NoPage from "./pages/NoPage";
import Chat from "./pages/chat/Chat";

initializeIcons();

export default function App() {
    return (
        <HashRouter>
            <Routes>
                <Route path="/">
                    <Route index element={<Chat />} />
                    <Route path="agent" element={<Chat isAgentMode={true} />} />
                    <Route path="*" element={<NoPage />} />
                </Route>
            </Routes>
        </HashRouter>
    );
}

// Initialize the chat buttons
document.addEventListener('DOMContentLoaded', () => {
    const talkToAgentBtn = document.getElementById('talkToAgentBtn');
    if (talkToAgentBtn) {
        talkToAgentBtn.addEventListener('click', () => {
            window.location.hash = '/agent';
        });
    }
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
