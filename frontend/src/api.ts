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
}

export interface SearchHit {
  file_id: string;
  path: string;
  line: number;
  snippet: string;
  url: string;
}

export interface SearchResponse {
  hits: SearchHit[];
  total: number;
  took_ms: number;
}

export async function searchTex(payload: SearchRequest): Promise<SearchResponse> {
  const response = await axios.post<SearchResponse>('/api/search', payload);
  return response.data;
}
