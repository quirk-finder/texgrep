import axios from 'axios';

export type SearchMode = 'literal' | 'regex';

export interface SearchFilters {
  year?: string;
  source?: string;
}

export interface SearchRequest {
  q: string;
  mode: SearchMode;
  filters?: SearchFilters;
  page?: number;
  size?: number;
  cursor?: string;
}

export type SnippetBlock =
  | { kind: 'text'; html: string }
  | { kind: 'math'; tex: string; display?: boolean; marked?: boolean };

export interface SearchHit {
  file_id: string;
  path: string;
  line: number;
  snippet?: string;
  url: string;
  blocks?: SnippetBlock[];
}

export interface SearchResponse {
  hits: SearchHit[];
  total: number;
  took_provider_ms: number;
  took_end_to_end_ms: number;
  page: number;
  size: number;
  next_cursor?: string | null;
}

export async function searchTex(payload: SearchRequest): Promise<SearchResponse> {
  const response = await axios.post<SearchResponse>('/api/search', payload);
  return response.data;
}
