import { Attachment, CardFactory } from "botbuilder";
import { Citation, CardType } from "../model";

export function actionBuilder(citation: Citation, docId: number): any {

    const urlParts = citation.url.split("]");
    let url = urlParts[urlParts.length - 1].replaceAll("(", "").replaceAll(")", "");
    let title = citation.title.replaceAll("/documents/", "");
    let content = citation.content.replaceAll(citation.title, "").replaceAll("url", "");
    console.log(docId);
    content = content.replaceAll(/(<([^>]+)>)/ig, "\n").replaceAll("<>", "");
    console.log(content);
    console.log("====================================\n\n");
    let citationCardAction = {
        title: `Ref${docId}`,
        type: CardType.ShowCard,
        card: {
            type: CardType.AdaptiveCard,
            body: [
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

            },{
                type: 'ActionSet',
                actions: []
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
    citations.map((citation: Citation) => {
        citationActions.push(actionBuilder(citation, docId));
        deleteEnd += `[${docId}]`;
        assistantAnswer = assistantAnswer.replaceAll(`[doc${docId}]`, `[${docId}]`);
        docId++;
    });
    assistantAnswer = assistantAnswer.replaceAll(deleteEnd, "");
    let answerCard = CardFactory.adaptiveCard(cardBodyBuilder(citationActions, assistantAnswer));
    return answerCard;
}