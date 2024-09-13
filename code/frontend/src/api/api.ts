import { ChatMessage, Conversation, ConversationRequest } from "./models";
const principalID = "00000000-0000-0000-0000-000000000000";
export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const response = await fetch("/api/conversation", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages: options.messages,
      conversation_id: options.id,
    }),
    signal: abortSignal,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(JSON.stringify(errorData.error));
  }

  return response;
}

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  try {
    const response = await fetch("/.auth/me");
    if (!response.ok) {
      console.log(
        "No identity provider found. Access to chat will be blocked."
      );
      return [];
    }
    const payload = await response.json();
    return payload;
  } catch (e) {
    return [];
  }
}

export async function getAssistantTypeApi() {
  try {
    const response = await fetch("/api/assistanttype", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    const config = await response.json(); // Parse JSON response
    return config;
  } catch (error) {
    console.error("Failed to fetch configuration:", error);
    return null; // Return null or some default value in case of error
  }
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const response = await fetch("/api/history/read", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": principalID,
    },
  })
    .then(async (res) => {
      if (!res) {
        return [];
      }
      const payload = await res.json();
      const messages: ChatMessage[] = [];
      if (payload?.messages) {
        payload.messages.forEach((msg: any) => {
          const message: ChatMessage = {
            id: msg.id,
            role: msg.role,
            date: msg.createdAt,
            content: msg.content,
            feedback: msg.feedback ?? undefined,
          };
          messages.push(message);
        });
      }
      return messages;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      return [];
    });
  return response;
};

export const historyList = async (
  offset = 0
): Promise<Conversation[] | null> => {
  let response = await fetch(`/api/history/list?offset=${offset}`, {
    method: "GET",
    headers: {
      "X-Ms-Client-Principal-Id": principalID,
    },
  })
    .then(async (res) => {
      console.log("list res", res);

      let payload = await res.json();
      console.log("History list api called", res, payload);
      if (!Array.isArray(payload)) {
        console.error("There was an issue fetching your data.");
        return null;
      }
      console.log("payload", payload);
      // static data
      //   payload =[
      //     {
      //         "_attachments": "attachments/",
      //         "_etag": "\"0200607a-0000-0200-0000-66e1e8400000\"",
      //         "_rid": "QedyANGSTVRcAQAAAAAAAA==",
      //         "_self": "dbs/QedyAA==/colls/QedyANGSTVQ=/docs/QedyANGSTVRcAQAAAAAAAA==/",
      //         "_ts": 1726081088,
      //         "createdAt": "2024-08-22T09:51:00.268537",
      //         "id": "affe98de-0adc-4aad-a68f-b53ded29a22f",
      //         "title": "dfsdf Investmsdsdfxcxd ent Portfolio Analysis",
      //         "type": "conversation",
      //         "updatedAt": "2024-08-22T09:51:11.226404",
      //         "userId": "84d3652d-7b78-4e33-bfe3-1bb6cd6c03a9"
      //     }
      // ]
      const conversations: Conversation[] = await Promise.all(
        payload.map(async (conv: any) => {
          let convMessages: ChatMessage[] = [];
          convMessages = await historyRead(conv.id)
            .then((res) => {
              return res;
            })
            .catch((err) => {
              console.error("error fetching messages: ", err);
              return [];
            });
          console.log("conversation messages", convMessages);

          const conversation: Conversation = {
            id: conv.id,
            title: conv.title,
            date: conv.createdAt,
            updatedAt: conv?.updatedAt,
            messages: convMessages,
          };
          return conversation;
        })
      );
      return conversations;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.", _err);
      return null;
    });
  console.log("list response returning ", response);
  return response;
};

export const historyUpdate = async (
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  const response = await fetch("/api/history/update", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": principalID,
    },
  })
    .then(async (res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  const response = await fetch("/api/history/rename", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      title: title,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": principalID, //need to changes
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyDelete = async (convId: string): Promise<Response> => {
  const response = await fetch("/api/history/delete", {
    method: "DELETE",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": principalID,
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};
