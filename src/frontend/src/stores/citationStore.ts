import { create } from "zustand";
import type { Citation } from "../api/models";

interface CitationState {
    activeCitation: Citation | null;
    isCitationPanelOpen: boolean;

    setActiveCitation: (citation: Citation | null) => void;
    openCitationPanel: (citation: Citation) => void;
    closeCitationPanel: () => void;
}

export const useCitationStore = create<CitationState>((set) => ({
    activeCitation: null,
    isCitationPanelOpen: false,

    setActiveCitation: (citation) => set({ activeCitation: citation }),
    openCitationPanel: (citation) =>
        set({ activeCitation: citation, isCitationPanelOpen: true }),
    closeCitationPanel: () =>
        set({ activeCitation: null, isCitationPanelOpen: false }),
}));
