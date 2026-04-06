export interface AdminSettings {
    function_url: string;
    function_key: string;
}

export interface Document {
    id: string;
    filename: string;
    title: string;
    source: string;
    chunk_count: number;
}

export interface ConfigSection {
    [key: string]: unknown;
}

export interface AppConfig {
    prompts: ConfigSection;
    embedding: ConfigSection;
    document_processors: Array<Record<string, unknown>>;
    integrated_vectorization_config: ConfigSection | null;
    logging: ConfigSection;
}
