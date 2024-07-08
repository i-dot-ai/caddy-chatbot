import { createEmbeddings } from "./embeddings";
import { loadTextFile } from "./loader";
import { createNewIndex } from "./searchIndex";
import { indexDoc } from "./searchIndexer";
import { split } from "./splitter";

async function main() {
  // Only need to call once
  await createNewIndex();

  // local files as source input
  const files = [`${__dirname}'/data/Contoso_Electronics_Company_Overview.md`];
  for (const file of files) {
    // load file
    const fullContent = loadTextFile(file);

    // split into chunks
    const contents = split(fullContent, 1000, 100);
    let partIndex = 0;
    for (const content of contents) {
      partIndex ++;
      // create embeddings
      const embeddings = await createEmbeddings(content);

      // upload to index
      await indexDoc({
        id: `${file.replace(/[^a-z0-9]/ig, "")}___${partIndex}`,
        content: content,
        filepath: file,
        contentVector: embeddings,
      });
    }
  }
}

main().then().finally();