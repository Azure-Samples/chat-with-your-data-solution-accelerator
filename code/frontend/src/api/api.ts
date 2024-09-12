import { ChatMessage, Conversation, ConversationRequest } from "./models";

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
      conversation_id: "7f09b86a-7853-4fa1-9e4d-0d582a3e4b69",
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": "95647817-dfb9-47a6-a124-4205938bdd72",
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
      "X-Ms-Client-Principal-Id": "4b16c510-aecd-4016-9581-5467bfe2b8f3",
    },
  })
    .then(async (res) => {
      let payload = await res.json();
      console.log("History list api called", res, payload);
      payload = [
        {
          _attachments: "attachments/",
          _etag: '"0500efd3-0000-0200-0000-66bfe1210000"',
          _rid: "F+9-AIq9dQHVngAAAAAAAA==",
          _self:
            "dbs/F+9-AA==/colls/F+9-AIq9dQE=/docs/F+9-AIq9dQHVngAAAAAAAA==/",
          _ts: 1723851041,
          createdAt: "2024-08-16T23:30:41.602059",
          id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
          title: "Data conversation title requested",
          type: "conversation",
          updatedAt: "2024-08-16T23:30:41.623074",
          userId: "00000000-0000-0000-0000-000000000000",
        },
      ];
      if (!Array.isArray(payload)) {
        console.error("There was an issue fetching your data.");
        return null;
      }
      console.log("payload", payload);
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
  // response = [
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-10T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-09-10T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-09T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-09-02T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-09T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-09-11T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-08T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-07T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-15T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-06T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-14T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-14T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-08-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-08-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  //   {
  //     id: "67eb8b48-10d2-46f9-bfae-e35c0de10971",
  //     updatedAt: "2024-09-01T05:28:11.040548",
  //     title: "Data conversation title requested",
  //     date: "2024-08-16T23:30:41.602059",
  //     messages: [],
  //   },
  // ];
  // response = [];
  return response;
};

export const historyUpdate = async (messages: ChatMessage[], convId: string): Promise<Response> => {
  const response = await fetch('/history/update', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(async res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}
