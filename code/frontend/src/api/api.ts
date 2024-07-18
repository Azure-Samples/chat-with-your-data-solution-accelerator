import { msalInstance } from "..";
import { loginRequest } from "../authConfig";
import { ConversationRequest } from "./models";

export async function customConversationApi(options: ConversationRequest, abortSignal: AbortSignal): Promise<Response> {
    const account = msalInstance.getActiveAccount();
    if (!account) {
        throw Error("No active account! Verify a user has been signed in and setActiveAccount has been called.");
    }

    const responseToken = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: account
    });

    const response = await fetch("/api/conversation/custom", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${responseToken.accessToken}`
        },
        body: JSON.stringify({
            messages: options.messages,
            conversation_id: options.id
        }),
        signal: abortSignal
    });

    return response;
}

export async function callConversationApi(options: ConversationRequest, abortSignal: AbortSignal): Promise<Response> {
    const response = await fetch("/api/conversation", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${responseToken.accessToken}`
        },
        body: JSON.stringify({
            messages: options.messages,
            conversation_id: options.id
        }),
        signal: abortSignal
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData.error));
    }

    return response;
}

export async function fetchServerConfigApi(): Promise<Response> {
    const account = msalInstance.getActiveAccount();
    if (!account) {
        throw Error("No active account! Verify a user has been signed in and setActiveAccount has been called.");
    }

    const responseToken = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: account
    });

    const response = await fetch("/api/config", {
        method: "get",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${responseToken.accessToken}`
        }
    });

    if (!response.ok) {
        throw new Error("Network response was not ok");
      }

    return response;
}
