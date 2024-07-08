import { AzureKeyCredential, SearchClient } from "@azure/search-documents";

export interface Doc {
  id: string,
  content: string,
  filepath: string,
  contentVector: number[]
}

const endpoint = "<your-search-endpoint>";
const apiKey = "<your-search-key>";
const indexName = "<your-index-name>";
const searchClient: SearchClient<Doc> = new SearchClient<Doc>(endpoint, indexName, new AzureKeyCredential(apiKey));

export async function indexDoc(doc: Doc): Promise<boolean> {
  const response = await searchClient.mergeOrUploadDocuments([doc]);
  return response.results.every((result) => result.succeeded);
}