import os
import re
import pandas as pd
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

def chunk_text(text, max_chunk_size=500):
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0
        
        current_chunk.append(word)
        current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def create_embeddings(client, chunks):
    embeddings = []
    for chunk in chunks:
        response = client.embeddings(
            input=chunk,
            engine="text-embedding-3-large"
        )
        embeddings.append(response['data'][0]['embedding'])
    
    return embeddings

def read_text_from_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def embed_chunk(chunk, embed_model):
    return embed_model.embeddings.create(input = chunk, model="text-embedding-3-large").data[0].embedding
    
def main(file_path):
    text = read_text_from_file(file_path=str(file_path))
    chunks = chunk_text(text)
    client = AzureOpenAI(
            api_key = os.getenv("AZURE_OPENAI_EMBED_API_KEY"), 
            api_version = "2024-02-01",
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        )

    embeddings = [embed_chunk(chunk,client) for chunk in chunks]
        
    data = {
            'chunk': chunks,
            'embedding': embeddings
        }
        
    df = pd.DataFrame(data)

    df.to_csv('new_embeddings.csv', index=False)
    print("Embeddings stored successfully!")

if __name__ == "__main__":
    main(file_path=input())