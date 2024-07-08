import * as fs from "node:fs";

export function loadTextFile(path: string): string {
  return fs.readFileSync(path, "utf-8");
}