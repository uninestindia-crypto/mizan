// Reading dotenv files picked or dropped in Settings. The engine parses them; this only turns bytes into text.

/** Matches the engine's per-file limit. A real .env is a few hundred bytes; anything near this is the wrong file. */
export const MAX_ENV_FILE_BYTES = 200_000;
export const MAX_ENV_FILES = 10;

export interface EnvUpload {
  name: string;
  text: string;
}

/**
 * Decode a dotenv file's bytes.
 *
 * Windows PowerShell 5 writes `>` redirects as UTF-16 with a byte-order mark, and Notepad can save UTF-8 with one.
 * `file.text()` would turn the first into garbage and leave the second's BOM glued to the first key's name, so the
 * encoding is read from the bytes instead.
 */
export function decodeEnvBytes(bytes: Uint8Array): string {
  const [a, b, c] = bytes;
  if (a === 0xef && b === 0xbb && c === 0xbf) return new TextDecoder("utf-8").decode(bytes.subarray(3));
  if (a === 0xff && b === 0xfe) return new TextDecoder("utf-16le").decode(bytes.subarray(2));
  if (a === 0xfe && b === 0xff) return new TextDecoder("utf-16be").decode(bytes.subarray(2));
  // No mark, but a NUL right after the first ASCII character is how UTF-16LE text looks.
  if (bytes.length >= 2 && a !== 0 && b === 0) return new TextDecoder("utf-16le").decode(bytes);
  return new TextDecoder("utf-8").decode(bytes);
}

export interface ReadEnvFiles {
  uploads: EnvUpload[];
  /** Plain-language reasons some files were left out. File names only, never contents. */
  problems: string[];
}

/** Read the chosen files, skipping any that are too large to be a dotenv file or that exceed the file count. */
export async function readEnvFiles(files: readonly File[]): Promise<ReadEnvFiles> {
  const uploads: EnvUpload[] = [];
  const problems: string[] = [];
  for (const file of files) {
    if (uploads.length >= MAX_ENV_FILES) {
      problems.push(`Only the first ${MAX_ENV_FILES} files were read; ${file.name} was left out.`);
      continue;
    }
    if (file.size > MAX_ENV_FILE_BYTES) {
      problems.push(`${file.name} is too large to be a .env file, so it was left out.`);
      continue;
    }
    try {
      uploads.push({ name: file.name, text: decodeEnvBytes(new Uint8Array(await file.arrayBuffer())) });
    } catch {
      problems.push(`${file.name} could not be read.`);
    }
  }
  return { uploads, problems };
}
