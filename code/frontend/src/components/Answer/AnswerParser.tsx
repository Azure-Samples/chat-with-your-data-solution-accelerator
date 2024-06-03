import { AskResponse, Citation } from "../../api";
import { cloneDeep } from "lodash-es";


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
};

let filteredCitations = [] as Citation[];

// Define a function to check if a citation with the same Chunk_Id already exists in filteredCitations
const isDuplicate = (citation: Citation,citationIndex:string) => {
    return filteredCitations.some((c) => c.chunk_id === citation.chunk_id) && !filteredCitations.find((c) => c.id === citationIndex) ;
};

export function parseAnswer(answer: AskResponse): ParsedAnswer {
    let answerText = answer.answer;
    const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g);

    const lengthDocN = "[doc".length;

    filteredCitations = [] as Citation[];
    let citationReindex = 0;
    let i =0
    citationLinks?.forEach(link => {
        // Replacing the links/citations with number
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        let citation = cloneDeep(answer.citations[i]) as Citation;
        if (!isDuplicate(citation, citationIndex)) {
          answerText = answerText.replaceAll(link, ` ^${++citationReindex}^ `);
          citation.id = citationIndex; // original doc index to de-dupe
          citation.reindex_id = citationReindex.toString(); // reindex from 1 for display
          filteredCitations.push(citation);
          i++
        }else{
            // Replacing duplicate citation with original index
            filteredCitations.find((ct)=>{
                if (citation.chunk_id == ct.chunk_id){
                    answerText= answerText.replaceAll(link, ` ^${ct.reindex_id}^`)
                }
            })
            i++
        }
    })


    return {
        citations: filteredCitations,
        markdownFormatText: answerText
    };
}
