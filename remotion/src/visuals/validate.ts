/**
 * Validate visual specs with the renderer's own Zod schema.
 *
 *   echo '[{"type":"array","values":[1,2],"algorithm":"merge-sort"}]' \
 *     | npx tsx src/visuals/validate.ts
 *
 * Reads a JSON array on stdin and writes a JSON array of
 * {ok:true} | {ok:false,error:"path: message; ..."} on stdout, one entry per
 * input. `null` means "no visual" and counts as ok. Exits non-zero when stdin
 * is not a JSON array, so the caller can tell "invalid spec" from "validator
 * did not run".
 */
import { VisualSpecSchema } from "../visualAdapter";

/**
 * zod wraps union failures in an `invalid_union` issue whose real problems live
 * under `errors` (one list per branch). Branch mismatches have no nested issues,
 * so they are skipped; leaves are reported as "path: message".
 */
const flatten = (issues: readonly any[], out: string[] = []): string[] => {
  for (const issue of issues) {
    if (out.length >= 3) break;
    if (issue.errors && issue.errors.length > 0) {
      for (const branch of issue.errors) flatten(branch, out);
    } else if (!issue.errors) {
      const path = (issue.path ?? []).map(String).join(".") || "spec";
      out.push(`${path}: ${issue.message ?? "invalid"}`);
    }
  }
  return out;
};

const readStdin = async (): Promise<string> => {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as string));
  }
  return Buffer.concat(chunks).toString("utf8");
};

const main = async (): Promise<void> => {
  let items: unknown = null;
  try {
    items = JSON.parse(await readStdin());
  } catch (error) {
    console.error(`stdin is not valid JSON: ${(error as Error).message}`);
    process.exit(2);
  }

  if (!Array.isArray(items)) {
    console.error("stdin must be a JSON array of visual specs");
    process.exit(2);
  }

  const results = items.map((item) => {
    if (item === null) return { ok: true };
    const parsed = VisualSpecSchema.safeParse(item);
    if (parsed.success) return { ok: true };
    const error = flatten(parsed.error.issues).join("; ");
    return { ok: false, error: error || "spec: invalid" };
  });

  process.stdout.write(JSON.stringify(results) + "\n");
};

void main();
