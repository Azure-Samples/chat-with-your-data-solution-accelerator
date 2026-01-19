import { AskResponse, Citation } from "../../api";
import { cloneDeep } from "lodash-es";


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
};

let filteredCitations = [] as Citation[];

// Define a function to check if a citation with the same Chunk_Id already exists in filteredCitations
const isDuplicate = (citation: Citation,citationIndex:string) => {
    return filteredCitations.some((c) => c.chunk_id === citation.chunk_id && c.id === citation.id) ;
};

export function parseAnswer(answer: AskResponse): ParsedAnswer {
    let answerText = answer.answer;
    const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g);

    const lengthDocN = "[doc".length;

    filteredCitations = [] as Citation[];
    let citationReindex = 0;

    // Track the last citation to detect consecutive duplicates
    let lastCitationKey: string | null = null;

    citationLinks?.forEach(link => {
        // Extract citation index from [docN]
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        let citation = cloneDeep(answer.citations[Number(citationIndex) - 1]) as Citation;

        if (citation === undefined) {
            answerText = answerText.replace(link, '');
            return;
        }

        // Create unique key for this citation
        const citationKey = `${citation.chunk_id}_${citation.id}`;

        // Check if this is a consecutive duplicate
        if (citationKey === lastCitationKey) {
            // Remove consecutive duplicate
            answerText = answerText.replace(link, '');
        } else {
            // Not a duplicate or not consecutive - process it
            if (!isDuplicate(citation, citationIndex)) {
                // This is a new unique citation - add to list
                citation.reindex_id = (++citationReindex).toString();
                filteredCitations.push(citation);
            } else {
                // This citation was seen before (but not consecutive) - find its reindex_id
                const existingCitation = filteredCitations.find(
                    (c) => c.chunk_id === citation.chunk_id && c.id === citation.id
                );
                if (existingCitation) {
                    citation.reindex_id = existingCitation.reindex_id;
                } else {
                    // Fallback: should not happen, but handle it
                    citation.reindex_id = (++citationReindex).toString();
                    filteredCitations.push(citation);
                }
            }

            // Replace with the citation number (use replace to only replace first occurrence)
            if (citation.reindex_id) {
                answerText = answerText.replace(link, ` ^${citation.reindex_id}^ `);
            }
        }

        // Update last citation key
        lastCitationKey = citationKey;
    });


    return {
        citations: filteredCitations,
        markdownFormatText: answerText
    };
}
