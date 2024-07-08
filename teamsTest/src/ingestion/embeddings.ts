import { OpenAIEmbeddings } from "@microsoft/teams-ai";

const embeddingClient = new OpenAIEmbeddings({
  azureApiKey: "a877928388654d678aab2e5014c96c3a",
  azureEndpoint: "https://oai-i-dot-ai-playground-sweden.openai.azure.com/",
  azureDeployment: "text-embedding-3-large"
});

export async function createEmbeddings(content: string): Promise<number[]> {
  const response = await embeddingClient.createEmbeddings("text-embedding-3-large", content);
  return response.output[0];
}