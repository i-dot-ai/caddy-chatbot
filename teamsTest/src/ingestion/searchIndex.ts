import { SearchIndexClient, AzureKeyCredential, SearchIndex } from "@azure/search-documents";

const endpoint = "<your-search-endpoint>";
const apiKey = "<your-search-key>";
const indexName = "<your-index-name>";

const indexDef: SearchIndex = {
  name: indexName,
  fields: [
    {
      type: "Edm.String",
      name: "id",
      key: true,
    },
    {
      type: "Edm.String",
      name: "content",
      searchable: true,
    },
    {
      type: "Edm.String",
      name: "filepath",
      searchable: true,
      filterable: true,
    },
    {
      type: "Collection(Edm.Single)",
      name: "contentVector",
      searchable: true,
      vectorSearchDimensions: 1536,
      vectorSearchProfileName: "default"
    }
  ],
  vectorSearch: {
    algorithms: [{
      name: "default",
      kind: "hnsw"
    }],
    profiles: [{
      name: "default",
      algorithmConfigurationName: "default"
    }]
  },
  semanticSearch: {
    defaultConfigurationName: "default",
    configurations: [{
      name: "default",
      prioritizedFields: {
        contentFields: [{
          name: "content"
        }]
      }
    }]
  }
};

export async function createNewIndex(): Promise<void> {
  const client = new SearchIndexClient(endpoint, new AzureKeyCredential(apiKey));
  await client.createIndex(indexDef);
}