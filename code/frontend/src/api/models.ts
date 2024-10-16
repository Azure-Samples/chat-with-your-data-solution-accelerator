export type AskResponse = {
    answer: string;
    citations: Citation[];
    error?: string;
};

export type Citation = {
    content: string;
    id: string;
    title: string | null;
    filepath: string | null;
    url: string | null;
    metadata: string | null | Record<string, string| number>;
    chunk_id: string | null | number;
    reindex_id?: string | null;
}

export type ToolMessageContent = {
    citations: Citation[];
    intent: string;
}

export type ChatMessage = {
  role: string;
  content: string;
  end_turn?: boolean;
  id: string;
  date: string;
  feedback?: Feedback;
  context?: string;
};

export enum Feedback {
  Neutral = "neutral",
  Positive = "positive",
  Negative = "negative",
  MissingCitation = "missing_citation",
  WrongCitation = "wrong_citation",
  OutOfScope = "out_of_scope",
  InaccurateOrIrrelevant = "inaccurate_or_irrelevant",
  OtherUnhelpful = "other_unhelpful",
  HateSpeech = "hate_speech",
  Violent = "violent",
  Sexual = "sexual",
  Manipulative = "manipulative",
  OtherHarmful = "other_harmlful",
}

export enum ChatCompletionType {
  ChatCompletion = "chat.completion",
  ChatCompletionChunk = "chat.completion.chunk",
}

export type ChatResponseChoice = {
    messages: ChatMessage[];
}

export type ChatResponse = {
    id: string;
    model: string;
    created: number;
    object: ChatCompletionType;
    choices: ChatResponseChoice[];
    error: string;
}

export type ConversationRequest = {
    id?: string;
    messages: ChatMessage[];
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  date: string;
  updatedAt?: string;
};

export type FrontEndSettings = {
  CHAT_HISTORY_ENABLED: boolean;
};
