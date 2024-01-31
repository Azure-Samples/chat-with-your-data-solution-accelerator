import { Attachment, CardFactory } from "botbuilder";
import { Citation, CardType } from "../model";

export function actionBuilder(citation: Citation, docId: number): any {

    const urlParts = citation.url.split("]");
    let url = urlParts[urlParts.length - 1].replaceAll("(", "").replaceAll(")", "");
    console.log(url);
    let citationCardAction = {
        title: `Ref${docId}`,
        type: CardType.ShowCard,
        card: {
            type: CardType.AdaptiveCard,
            body: [
                {
                    type: CardType.TextBlock,
                    text: citation.title,
                    wrap: true
                },
                {
                    type: CardType.TextBlock,
                    text: citation.content,
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

export function cwydResponseBuilder(citations: Citation[], assistantAnswer: string): Attachment {

    let citationActions: any[] = [];
    let docId = 1;
    citations.map((citation: Citation) => {
        citationActions.push(actionBuilder(citation, docId));
        assistantAnswer = assistantAnswer.replaceAll(
            `[doc${docId}]`,
            ""
        );
        docId++;
    });
    console.log(assistantAnswer);
    let answerCard = CardFactory.adaptiveCard({
        type: CardType.AdaptiveCard,
        body: [
            {
                type: CardType.TextBlock,
                text: assistantAnswer,
                wrap: true
            }
        ],
        actions: citationActions
    });
    return answerCard;
}