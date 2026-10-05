import { describe, expect, it } from "vitest";
import { decodeEnvBytes, MAX_ENV_FILES, MAX_ENV_FILE_BYTES, readEnvFiles } from "./envFile";

const TEXT = "NAME_ONE=value-one\r\nNAME_TWO=value-two\r\n";

function utf16(text: string, order: "le" | "be", mark: boolean): Uint8Array {
  const out: number[] = mark ? (order === "le" ? [0xff, 0xfe] : [0xfe, 0xff]) : [];
  for (const char of text) {
    const code = char.charCodeAt(0);
    out.push(...(order === "le" ? [code & 0xff, code >> 8] : [code >> 8, code & 0xff]));
  }
  return Uint8Array.from(out);
}

describe("decodeEnvBytes", () => {
  it("reads plain UTF-8", () => {
    expect(decodeEnvBytes(new TextEncoder().encode(TEXT))).toBe(TEXT);
  });

  it("drops a UTF-8 byte-order mark so it cannot stick to the first key", () => {
    const bytes = Uint8Array.from([0xef, 0xbb, 0xbf, ...new TextEncoder().encode(TEXT)]);
    const text = decodeEnvBytes(bytes);
    expect(text).toBe(TEXT);
    expect(text.startsWith("NAME_ONE")).toBe(true);
  });

  it("reads UTF-16 as PowerShell writes it, with or without the mark", () => {
    expect(decodeEnvBytes(utf16(TEXT, "le", true))).toBe(TEXT);
    expect(decodeEnvBytes(utf16(TEXT, "be", true))).toBe(TEXT);
    expect(decodeEnvBytes(utf16(TEXT, "le", false))).toBe(TEXT);
  });

  it("returns an empty string for an empty file", () => {
    expect(decodeEnvBytes(new Uint8Array())).toBe("");
  });
});

function fileOf(name: string, bytes: Uint8Array): File {
  return { name, size: bytes.length, arrayBuffer: async () => bytes.slice().buffer } as unknown as File;
}

describe("readEnvFiles", () => {
  it("decodes every file and keeps its name", async () => {
    const result = await readEnvFiles([fileOf(".env", new TextEncoder().encode("A=1\n")), fileOf(".env.local", utf16("B=2\n", "le", true))]);
    expect(result.uploads).toEqual([
      { name: ".env", text: "A=1\n" },
      { name: ".env.local", text: "B=2\n" },
    ]);
    expect(result.problems).toEqual([]);
  });

  it("leaves out a file that is too large, naming it but never its contents", async () => {
    const big = { name: "dump.bin", size: MAX_ENV_FILE_BYTES + 1, arrayBuffer: async () => new ArrayBuffer(0) } as unknown as File;
    const result = await readEnvFiles([big, fileOf(".env", new TextEncoder().encode("A=1\n"))]);
    expect(result.uploads.map((u) => u.name)).toEqual([".env"]);
    expect(result.problems).toEqual(["dump.bin is too large to be a .env file, so it was left out."]);
  });

  it("stops at the file-count limit", async () => {
    const many = Array.from({ length: MAX_ENV_FILES + 2 }, (_, i) => fileOf(`f${i}.env`, new TextEncoder().encode("A=1\n")));
    const result = await readEnvFiles(many);
    expect(result.uploads).toHaveLength(MAX_ENV_FILES);
    expect(result.problems).toHaveLength(2);
  });

  it("reports a file that cannot be read", async () => {
    const broken = { name: "x.env", size: 3, arrayBuffer: async () => Promise.reject(new Error("denied")) } as unknown as File;
    const result = await readEnvFiles([broken]);
    expect(result.uploads).toEqual([]);
    expect(result.problems).toEqual(["x.env could not be read."]);
  });
});
