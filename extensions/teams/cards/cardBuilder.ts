import { Attachment, CardFactory } from "botbuilder";
import { Citation, CardType } from "../model";

export function actionBuilder(citation: Citation, docId: number): any {

    const urlParts = citation.url.split("]");
    let url = urlParts[urlParts.length - 1].replaceAll("(", "").replaceAll(")", "");
    let title = citation.title.replaceAll("/documents/", "");
    let content = citation.content.replaceAll(citation.title, "").replaceAll("url", "");
    content = content.replaceAll(/(<([^>]+)>)/ig, "\n").replaceAll("<>", "");
    let citationCardAction = {
        title: `Ref${docId}`,
        type: CardType.ShowCard,
        card: {
            type: CardType.AdaptiveCard,
            body: [
                {
                    type: CardType.TextBlock,
                    text: `Reference - Part ${parseInt(citation.chunk_id) + 1}`,
                    wrap: true,
                    size: "small",
                },
                {
                    type: CardType.TextBlock,
                    text: title,
                    wrap: true,
                    weight: "Bolder",
                    size: "Large",
                },
                {
                    type: CardType.TextBlock,
                    text: content,
                    wrap: true
                }
            ],
            actions: [
                {
                    type: CardType.OpenUrl,
                    title: "Go to the source",
                    url: url,
                }
            ]
        }
    };

    return citationCardAction;
}
export function cardBodyBuilder(citations: any[], assistantAnswer: string): any {
    let answerCard = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        type: CardType.AdaptiveCard,
        body: [
            {
                type: CardType.TextBlock,
                text: assistantAnswer,
                wrap: true

            }, {
                type: 'ActionSet',
                actions: []
            }, {
                type: CardType.TextBlock,
                text: "AI-generated content may be incorrect",
                wrap: true,
                weight: "lighter",
                size: "small",
                color: "default"
            }
        ],
        actions: [],
        msteams: {
            width: "Full"
        }
    };
    if (citations.length <= 6) {
        answerCard["actions"] = citations;
    } else {
        const chunkSize = 5;
        for (let i = 0; i < citations.length; i += chunkSize) {
            const chunk = citations.slice(i, i + chunkSize);
            answerCard["body"].push({
                type: 'ActionSet',
                actions: chunk
            });
        }
    }

    return answerCard;
}
export function cwydResponseBuilder(citations: Citation[], assistantAnswer: string): Attachment {
    let citationActions: any[] = [];
    let docId = 1;
    let deleteEnd = "";
    let deleteEndSpace = "";
    let refCount = 1;
    let findPart = {};
    let reIndex = 0;
    citations.map((citation: Citation) => {
        if (!(citation.chunk_id in findPart)) {
            reIndex = docId;
            citationActions.push(actionBuilder(citation, reIndex));
            findPart[citation.chunk_id] = reIndex;
            docId++;
        } else {
            reIndex = findPart[citation.chunk_id];
        }

        deleteEnd += `[${reIndex}]`;
        deleteEndSpace += ` [${reIndex}]`;
        assistantAnswer = assistantAnswer.replaceAll(`[doc${refCount}]`, `[${reIndex}]`);

        refCount++;
    });
    assistantAnswer = assistantAnswer.replaceAll(deleteEnd, "");
    assistantAnswer = assistantAnswer.replaceAll(deleteEndSpace, "");
    let answerCard = CardFactory.adaptiveCard(cardBodyBuilder(citationActions, assistantAnswer));
    return answerCard;
}
