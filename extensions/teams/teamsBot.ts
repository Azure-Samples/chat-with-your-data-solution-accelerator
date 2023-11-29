import * as querystring from "querystring";
import {
  TeamsActivityHandler,
  CardFactory,
  TurnContext,
  MessagingExtensionAction,
  MessagingExtensionQuery,
  MessagingExtensionResponse,
  MessagingExtensionActionResponse,
  AppBasedLinkQuery,
  ActivityTypes,
  MessageFactory,
} from "botbuilder";
import rawWelcomeCard from "./adaptiveCards/welcome.json";
import { AdaptiveCards } from "@microsoft/adaptivecards-tools";

import axios from "axios";
import UserProfile from "./userProfile";
import config from "./config";
import {
  ChatMessage,
  Citation,
  ToolMessageContent,
  ChatResponse,
} from "./model";

export interface DataInterface {
  likeCount: number;
}

const CONVERSATION_DATA_PROPERTY = "conversationData";
const USER_PROFILE_PROPERTY = "userProfile";
const EMPTY_RESPONSE = "Sorry, I do not have an answer. Please try again.";

export class TeamsBot extends TeamsActivityHandler {
  // record the likeCount
  likeCountObj: { likeCount: number };
  conversationDataAccessor: any;
  userProfileAccessor: any;
  conversationState: any;
  userState: any;

  constructor(conversationState, userState) {
    super();

    let newActivity;
    let assistantAnswer = "";

    // Create the state property accessors for the conversation data and user profile.
    // Setting up a way for the bot to store and retrieve data that is specific to the current conversation
    this.conversationDataAccessor = conversationState.createProperty(
      CONVERSATION_DATA_PROPERTY
    );
    this.userProfileAccessor = userState.createProperty(USER_PROFILE_PROPERTY);

    // The state management objects for the conversation and user state.
    this.conversationState = conversationState;
    this.userState = userState;

    // Track of the number of likes in the context of the bot's operation.
    this.likeCountObj = { likeCount: 0 };

    this.onMessage(async (context, next) => {

      // Get the state properties from the turn context.
      const userProfile: UserProfile = await this.userProfileAccessor.get(
        context,
        {}
      );
      const conversationData = await this.conversationDataAccessor.get(
        context,
        {}
      );

      let txt = context.activity.text;
      const removedMentionText = TurnContext.removeRecipientMention(
        context.activity
      );
      if (removedMentionText) {
        // Remove the line break
        txt = removedMentionText.toLowerCase().replace(/\n|\r/g, "").trim();
      }

      // Trigger command by IM text
      switch (txt) {
        case "welcome": {
          const card =
            AdaptiveCards.declareWithoutData(rawWelcomeCard).render();
          await context.sendActivity({
            attachments: [CardFactory.adaptiveCard(card)],
          });
          break;
        }
        case "bye": {
          userProfile.messageId = crypto.randomUUID();
          await context.sendActivity("Good Bye!");
          // Clear out state
          await this.conversationState.delete(context);
          break;
        }
        case "exception": {
          assistantAnswer = "Test Exception thrown from the bot.";
          break;
        }
        default: {
          //Post the message to a REST API endpoint as a json string
          try {
            userProfile.messageId = context.activity.id;
            if (userProfile.waitingFor === "true") {
              const msg = "Please wait for a moment, I am still thinking ...";
              await context.sendActivity(msg);
            } else {
              const reply = await context.sendActivity("Searching ...");

              const typingReply = await context.sendActivities([
                { type: ActivityTypes.Typing },
              ]);

              userProfile.waitingFor = "true";
              await this.userState.saveChanges(context, false);

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
                          answers.push(
                            userMessage,
                            { role: "error", content: "ERROR: " + result.error + " | " + EMPTY_RESPONSE  }
                          );
                        } else {
                          answers.push(
                            userMessage,
                            ...result.choices[0].messages
                          );
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
                if (answer.role === "user") {
                } else if (answer.role === "assistant") {
                  assistantAnswer = answer.content;
                  if (assistantAnswer.startsWith("[doc")) {
                    assistantAnswer = EMPTY_RESPONSE;
                  } else {
                    const citations = parseCitationFromMessage(
                      answers[index - 1]
                    );
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
                  newActivity.typing = false; // Stop the ellipses visual indicator
                } else if (answer.role === "error") {
                  newActivity = MessageFactory.text(
                    "Sorry, an error occurred. Try waiting a few minutes. If the issue persists, contact your system administrator. Error: " +
                      answer.content
                  );
                  newActivity.id = reply.id;
                  newActivity.typing = false; // Stop the ellipses visual indicator
                }
              });
              await context.updateActivity(newActivity);

              await this.userState.saveChanges(context, false);
            }
          } catch (error) {
            // console.log(error);
          } finally {
            userProfile.waitingFor = "false";
          }

          break;
        }
        /**
         * case "yourCommand": {
         *   await context.sendActivity(`Add your response here!`);
         *   break;
         * }
         */
      }
      await context.sendTraceActivity(
        "OnMessage",
        `${txt}`,
        "https://www.botframework.com",
        "Turn Normal"
      );

      // By calling next() you ensure that the next BotHandler is run.
      await next();
    });

    this.onMembersAdded(async (context, next) => {
      const membersAdded = context.activity.membersAdded;
      for (let cnt = 0; cnt < membersAdded.length; cnt++) {
        if (membersAdded[cnt].id) {
          const card =
            AdaptiveCards.declareWithoutData(rawWelcomeCard).render();
          await context.sendActivity({
            attachments: [CardFactory.adaptiveCard(card)],
          });
          break;
        }
      }
      await next();
    });
  }

  /**
   * Override the ActivityHandler.run() method to save state changes after the bot logic completes.
   */
  async run(context) {
    await super.run(context);
    // Save any state changes. The load happened during the execution of the Dialog.
    await this.conversationState.saveChanges(context, false);
    await this.userState.saveChanges(context, false);
  }

  // Message extension Code
  // Action.
  public async handleTeamsMessagingExtensionSubmitAction(
    context: TurnContext,
    action: MessagingExtensionAction
  ): Promise<MessagingExtensionActionResponse> {
    switch (action.commandId) {
      case "createCard":
        return createCardCommand(context, action);
      case "shareMessage":
        return shareMessageCommand(context, action);
      default:
        throw new Error("NotImplemented");
    }
  }

  // Search.
  public async handleTeamsMessagingExtensionQuery(
    context: TurnContext,
    query: MessagingExtensionQuery
  ): Promise<MessagingExtensionResponse> {
    const searchQuery = query.parameters[0].value;
    const response = await axios.get(
      `http://registry.npmjs.com/-/v1/search?${querystring.stringify({
        text: searchQuery,
        size: 8,
      })}`
    );

    const attachments = [];
    response.data.objects.forEach((obj) => {
      const heroCard = CardFactory.heroCard(obj.package.name);
      const preview = CardFactory.heroCard(obj.package.name);
      preview.content.tap = {
        type: "invoke",
        value: { name: obj.package.name, description: obj.package.description },
      };
      const attachment = { ...heroCard, preview };
      attachments.push(attachment);
    });

    return {
      composeExtension: {
        type: "result",
        attachmentLayout: "list",
        attachments: attachments,
      },
    };
  }

  public async handleTeamsMessagingExtensionSelectItem(
    context: TurnContext,
    obj: any
  ): Promise<MessagingExtensionResponse> {
    return {
      composeExtension: {
        type: "result",
        attachmentLayout: "list",
        attachments: [CardFactory.heroCard(obj.name, obj.description)],
      },
    };
  }

  // Link Unfurling.
  public async handleTeamsAppBasedLinkQuery(
    context: TurnContext,
    query: AppBasedLinkQuery
  ): Promise<MessagingExtensionResponse> {
    const attachment = CardFactory.thumbnailCard(
      "Image Preview Card",
      query.url,
      [query.url]
    );
    return {
      composeExtension: {
        type: "result",
        attachmentLayout: "list",
        attachments: [attachment],
      },
    };
  }
}

async function createCardCommand(
  context: TurnContext,
  action: MessagingExtensionAction
): Promise<MessagingExtensionResponse> {
  // The user has chosen to create a card by choosing the 'Create Card' context menu command.
  const data = action.data;
  const heroCard = CardFactory.heroCard(data.title, data.text);
  heroCard.content.subtitle = data.subTitle;
  const attachment = {
    contentType: heroCard.contentType,
    content: heroCard.content,
    preview: heroCard,
  };

  return {
    composeExtension: {
      type: "result",
      attachmentLayout: "list",
      attachments: [attachment],
    },
  };
}

async function shareMessageCommand(
  context: TurnContext,
  action: MessagingExtensionAction
): Promise<MessagingExtensionResponse> {
  // The user has chosen to share a message by choosing the 'Share Message' context menu command.
  let userName = "unknown";
  if (
    action.messagePayload &&
    action.messagePayload.from &&
    action.messagePayload.from.user &&
    action.messagePayload.from.user.displayName
  ) {
    userName = action.messagePayload.from.user.displayName;
  }

  // This Message Extension example allows the user to check a box to include an image with the
  // shared message.  This demonstrates sending custom parameters along with the message payload.
  let images = [];
  const includeImage = action.data.includeImage;
  if (includeImage === "true") {
    images = [
      "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQtB3AwMUeNoq4gUBGe6Ocj8kyh3bXa9ZbV7u1fVKQoyKFHdkqU",
    ];
  }
  const heroCard = CardFactory.heroCard(
    `${userName} originally sent this message:`,
    action.messagePayload.body.content,
    images
  );

  if (
    action.messagePayload &&
    action.messagePayload.attachments &&
    action.messagePayload.attachments.length > 0
  ) {
    // This sample does not add the MessagePayload Attachments.  This is left as an
    // exercise for the user.
    heroCard.content.subtitle = `(${action.messagePayload.attachments.length} Attachments not included)`;
  }

  const attachment = {
    contentType: heroCard.contentType,
    content: heroCard.content,
    preview: heroCard,
  };

  return {
    composeExtension: {
      type: "result",
      attachmentLayout: "list",
      attachments: [attachment],
    },
  };
}
