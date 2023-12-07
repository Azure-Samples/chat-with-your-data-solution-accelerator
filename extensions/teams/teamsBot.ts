import {
  TeamsActivityHandler,
  CardFactory,
  TurnContext,
  AdaptiveCardInvokeValue,
  AdaptiveCardInvokeResponse,
  ActivityTypes,
  MessageFactory,
} from "botbuilder";
import config from "./config";
import {
  ChatMessage,
  ChatResponse,
  ToolMessageContent,
  Citation,
} from "./model";

const EMPTY_RESPONSE = "Sorry, I do not have an answer. Please try again.";

export class TeamsBot extends TeamsActivityHandler {
  constructor() {
    super();
    let newActivity;
    let assistantAnswer = "";

    this.onMessage(async (context, next) => {
      console.log("Running with Message Activity.");
      const removedMentionText = TurnContext.removeRecipientMention(
        context.activity
      );
      const txt = removedMentionText.toLowerCase().replace(/\n|\r/g, "").trim();
      try {
        const reply = await context.sendActivity("Searching ...");

        const typingReply = await context.sendActivities([
          { type: ActivityTypes.Typing },
        ]);

        // Create a new activity with the user's message as a reply.
        const answers: ChatMessage[] = [];
        const userMessage: ChatMessage = {
          role: "user",
          content: txt,
        };

        // Call the Azure Function to get the response from Azure OpenAI on your Data
        let result = {} as ChatResponse;
        try {
          const response = await fetch(config.azureFunctionUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              messages: [userMessage],
              conversation_id: "",
            }),
          });

          // Parse the response
          if (response?.body) {
            const reader = response.body.getReader();
            let runningText = "";
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              var text = new TextDecoder("utf-8").decode(value);
              const objects = text.split("\n");
              objects.forEach((obj) => {
                try {
                  runningText += obj;
                  result = JSON.parse(runningText);
                  if (result.error) {
                    answers.push(userMessage, {
                      role: "error",
                      content:
                        "ERROR: " + result.error + " | " + EMPTY_RESPONSE,
                    });
                  } else {
                    answers.push(userMessage, ...result.choices[0].messages);
                  }
                  runningText = "";
                } catch (e) {
                  const errorMessage: ChatMessage = {
                    role: "error",
                    content: e.message,
                  };
                  answers.push(errorMessage);
                }
              });
            }
          }
        } catch (e) {
          console.error(e);
          const errorMessage: ChatMessage = {
            role: "error",
            content: e.message,
          };
          answers.push(errorMessage);
        }

        // Parse the citations from the tool message
        const parseCitationFromMessage = (message: ChatMessage) => {
          if (message.role === "tool") {
            try {
              const toolMessage = JSON.parse(
                message.content
              ) as ToolMessageContent;
              return toolMessage.citations;
            } catch {
              return [];
            }
          }
          return [];
        };

        // Generate the response for the user
        answers.map((answer, index) => {
          if (answer.role === "assistant") {
            assistantAnswer = answer.content;
            if (assistantAnswer.startsWith("[doc")) {
              assistantAnswer = EMPTY_RESPONSE;
            } else {
              const citations = parseCitationFromMessage(answers[index - 1]);
              let docId = 1;
              citations.map((citation: Citation) => {
                const urlParts = citation.url.split("]");
                const url = urlParts[urlParts.length - 1];
                assistantAnswer = assistantAnswer.replaceAll(
                  `[doc${docId}]`,
                  `[[${citation.filepath}]${url}]`
                );
                docId++;
              });
            }
            newActivity = MessageFactory.text(assistantAnswer);
            newActivity.id = reply.id;
          } else if (answer.role === "error") {
            newActivity = MessageFactory.text(
              "Sorry, an error occurred. Try waiting a few minutes. If the issue persists, contact your system administrator. Error: " +
                answer.content
            );
            newActivity.id = reply.id;
          }
        });
        newActivity.typing = false; // Stop the ellipses visual indicator
        await context.updateActivity(newActivity);

        // await this.saveChanges(context, false);
      } catch (error) {
        // console.log(error);
      } finally {
      }

      // By calling next() you ensure that the next BotHandler is run.
      await next();
    });

    this.onMembersAdded(async (context, next) => {
      const membersAdded = context.activity.membersAdded;
      for (let cnt = 0; cnt < membersAdded.length; cnt++) {
        if (membersAdded[cnt].id) {
          await context.sendActivity(
            `Greetings! I am the Chat with your data bot. How can I help you today?`
          );
          break;
        }
      }
      await next();
    });
  }
}
