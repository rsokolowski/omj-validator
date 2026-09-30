/**
 * OMJ task keys ("2015_etap3_1") as the refine conversation shows them: the AI
 * names tasks by key - in a version's task list and as [[key]] in its reply.
 */

const TASK_KEY = /^(\d{4})_(etap[123])_(\d{1,2})$/;
const TASK_REF = /\[\[(\d{4}_etap[123]_\d{1,2})\]\]/g;
const ETAPS: Record<string, string> = { etap1: "I", etap2: "II", etap3: "III" };

export interface TaskRef {
  key: string;
  label: string;
  url: string;
}

export function taskRef(key: string): TaskRef | null {
  const match = TASK_KEY.exec(key);
  if (!match) return null;
  const [, year, etap, number] = match;
  return {
    key,
    label: `${year} · etap ${ETAPS[etap]} · zad. ${Number(number)}`,
    url: `/task/${year}/${etap}/${Number(number)}`,
  };
}

export type ReplyPart = { text: string } | { task: TaskRef };

/** Split a reply into text and task references, to render the tasks as links. */
export function splitTaskRefs(reply: string): ReplyPart[] {
  const parts: ReplyPart[] = [];
  let last = 0;
  for (const match of reply.matchAll(TASK_REF)) {
    const ref = taskRef(match[1]);
    if (!ref) continue;
    if (match.index > last) parts.push({ text: reply.slice(last, match.index) });
    parts.push({ task: ref });
    last = match.index + match[0].length;
  }
  if (last < reply.length) parts.push({ text: reply.slice(last) });
  return parts;
}
