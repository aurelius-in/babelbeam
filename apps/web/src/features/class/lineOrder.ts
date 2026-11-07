/** Teacher-side line numbering. Lines upload in parallel; listeners reorder by seq. */
export type OutgoingLine = {
  seq: number;
  waitFor: number[];
};

export type LineOrder = {
  begin: () => OutgoingLine;
  end: (seq: number) => void;
  pending: () => number;
  reset: () => void;
};

export const MAX_WAIT_FOR = 8;

export function createLineOrder(): LineOrder {
  let last = 0;
  const inFlight = new Set<number>();
  return {
    begin() {
      last += 1;
      const waitFor = [...inFlight].sort((left, right) => left - right).slice(-MAX_WAIT_FOR);
      inFlight.add(last);
      return { seq: last, waitFor };
    },
    end(seq) {
      inFlight.delete(seq);
    },
    pending: () => inFlight.size,
    reset() {
      last = 0;
      inFlight.clear();
    },
  };
}

export function lineHeaders(line: OutgoingLine): Record<string, string> {
  const headers: Record<string, string> = { "X-Line-Seq": String(line.seq) };
  if (line.waitFor.length > 0) {
    headers["X-Line-Wait"] = line.waitFor.join(",");
  }
  return headers;
}

/** First in, first out gate that lets at most `limit` uploads run at once. */
export function createUploadGate(limit: number): { run: <T>(task: () => Promise<T>) => Promise<T> } {
  let active = 0;
  const waiting: Array<() => void> = [];
  function release() {
    const next = waiting.shift();
    if (next) {
      next();
    } else {
      active -= 1;
    }
  }
  return {
    async run(task) {
      if (active >= limit) {
        await new Promise<void>((resolve) => waiting.push(resolve));
      } else {
        active += 1;
      }
      try {
        return await task();
      } finally {
        release();
      }
    },
  };
}
