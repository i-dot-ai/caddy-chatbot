// split words by delimiters.
const delimiters = [" ", "\t", "\r", "\n"];

export function split(content: string, length: number, overlap: number): Array<string> {
  const results = new Array<string>();
  let cursor = 0, curChunk = 0;
  results.push("");
  while(cursor < content.length) {
    const curChar = content[cursor];
    if (delimiters.includes(curChar)) {
      // check chunk length
      while (curChunk < results.length && results[curChunk].length >= length) {
        curChunk ++;
      }
      for (let i = curChunk; i < results.length; i++) {
        results[i] += curChar;
      }
      if (results[results.length - 1].length >= length - overlap) {
        results.push("");
      }
    } else {
      // append
      for (let i = curChunk; i < results.length; i++) {
        results[i] += curChar;
      }
    }
    cursor ++;
  }
  while (curChunk < results.length - 1) {
    results.pop();
  }
  return results;
}