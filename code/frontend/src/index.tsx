import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initializeIcons } from "@fluentui/react";

import "./index.css";

import {
    PublicClientApplication,
    EventType,
    EventMessage,
    AuthenticationResult,
} from "@azure/msal-browser";
import { msalConfig } from "./authConfig";

initializeIcons();

export const msalInstance = new PublicClientApplication(msalConfig);

msalInstance.initialize().then(() => {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
        msalInstance.setActiveAccount(accounts[0]);
    }

    msalInstance.addEventCallback((event: EventMessage) => {
        if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const payload = event.payload as AuthenticationResult;
            const account = payload.account;
            msalInstance.setActiveAccount(account);
        }
    });

    const root = ReactDOM.createRoot(
        document.getElementById("root") as HTMLElement
    );
    root.render(
        <React.StrictMode>
            <App pca={msalInstance} />
        </React.StrictMode>
    );
});
