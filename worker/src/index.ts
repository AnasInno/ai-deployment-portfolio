type Env = Record<string, never>;

const startedAt = Date.now();
const repoUrl = "https://github.com/AnasInno/ai-deployment-portfolio";
const gatewaySourceUrl = `${repoUrl}/tree/main/gateway`;

const documents = [
  {
    id: "teachclaw-workflow",
    tags: ["teacher-workflow", "deployment", "artifacts"],
    text: "TeachClaw routes teacher requests into worksheets, lesson decks, marking, feedback and generated classroom artifacts.",
  },
  {
    id: "gateway-readiness",
    tags: ["evals", "readiness", "audit"],
    text: "The AI Deployment Gateway demonstrates source-grounded retrieval, eval runs, SQLite persistence, audit events, readiness gates and rollback plans.",
  },
  {
    id: "story-trials",
    tags: ["full-stack", "testing"],
    text: "Story Trials implemented a Next.js frontend, Express API, Prisma PostgreSQL database, IPFS metadata flow and Story Protocol testnet integration.",
  },
];

const auditEvents = [
  { type: "deployment_registered", deployment_id: "teachclaw-local", actor: "portfolio-demo", timestamp: "2026-05-03T22:45:00Z" },
  { type: "eval_run_completed", deployment_id: "teachclaw-local", status: "pass", pass_rate: 1, timestamp: "2026-05-03T22:46:00Z" },
  { type: "readiness_checked", deployment_id: "teachclaw-local", status: "pass", timestamp: "2026-05-03T22:47:00Z" },
];

function json(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    ...init,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      ...init.headers,
    },
  });
}

function docs() {
  return new Response(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Deployment Gateway Demo</title>
  <style>
    body { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f4ef; color: #171717; }
    main { max-width: 860px; margin: 0 auto; padding: 56px 22px; }
    h1 { font-size: 38px; margin: 0 0 12px; }
    p { color: #4b5563; line-height: 1.65; }
    a { color: #0f766e; font-weight: 700; }
    code, pre { background: #111827; color: #f9fafb; border-radius: 8px; }
    pre { padding: 18px; overflow-x: auto; }
    li { margin: 10px 0; }
  </style>
</head>
<body>
  <main>
    <h1>AI Deployment Gateway Demo</h1>
    <p>This is the live public API surface for Anas Abdi's AI deployment portfolio. The full Docker/FastAPI implementation lives in the public repo; this Worker keeps a small always-on reviewer demo available without exposing private TeachClaw code or secrets.</p>
    <p><a href="${gatewaySourceUrl}">Gateway source</a> / <a href="https://anasinno.github.io/ai-deployment-portfolio/">Portfolio</a></p>
    <h2>Try It</h2>
    <ul>
      <li><a href="/health">/health</a></li>
      <li><a href="/metrics">/metrics</a></li>
      <li><a href="/deployments/teachclaw-local/readiness">/deployments/teachclaw-local/readiness</a></li>
      <li><a href="/audit/events">/audit/events</a></li>
    </ul>
    <pre>curl -X POST ${"https://ai-deployment-gateway-demo.anasinno.workers.dev"}/ask \\
  -H 'content-type: application/json' \\
  -d '{"question":"What does TeachClaw route?"}'</pre>
  </main>
</body>
</html>`, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "access-control-allow-origin": "*",
    },
  });
}

function tokens(text: string) {
  return new Set(text.toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter(Boolean));
}

function retrieve(question: string) {
  const q = tokens(question);
  return documents
    .map((doc) => {
      const d = tokens(`${doc.id} ${doc.tags.join(" ")} ${doc.text}`);
      let score = 0;
      for (const token of q) if (d.has(token)) score += 1;
      return { ...doc, score };
    })
    .sort((a, b) => b.score - a.score)
    .filter((doc) => doc.score > 0)
    .slice(0, 3);
}

async function readJson(request: Request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

export default {
  async fetch(request: Request, _env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "content-type,x-api-key",
        },
      });
    }

    if (url.pathname === "/" || url.pathname === "/docs") return docs();

    if (url.pathname === "/health" && request.method === "GET") {
      return json({
        status: "ok",
        service: "ai-deployment-gateway-demo",
        implementation: "cloudflare-worker-live-surface",
        fastapi_source: gatewaySourceUrl,
        documents: documents.length,
        deployments: 1,
        eval_runs: 1,
        uptime_seconds: Math.round((Date.now() - startedAt) / 1000),
      });
    }

    if (url.pathname === "/metrics" && request.method === "GET") {
      return json({
        documents: documents.length,
        deployments: 1,
        eval_runs: 1,
        audit_events: auditEvents.length,
        readiness_status: "pass",
        public_write_mode: "disabled",
      });
    }

    if (url.pathname === "/audit/events" && request.method === "GET") {
      return json({ events: auditEvents });
    }

    if (url.pathname === "/deployments/teachclaw-local/readiness" && request.method === "GET") {
      return json({
        deployment_id: "teachclaw-local",
        status: "pass",
        reason: "Latest demo eval passes the configured threshold.",
        required_eval_pass_rate: 1,
        latest_eval_pass_rate: 1,
        rollback_plan: "Revert to last validated route bundle and rerun gateway smoke tests.",
      });
    }

    if (url.pathname === "/ask" && request.method === "POST") {
      const body = await readJson(request) as { question?: string };
      const question = body.question || "";
      const matches = retrieve(question);
      return json({
        question,
        answer: matches.length
          ? `Top source: ${matches[0].id}. ${matches[0].text}`
          : "No relevant source found in the public demo corpus.",
        sources: matches.map(({ id, tags, text, score }) => ({ id, tags, text, score })),
      });
    }

    if (url.pathname === "/eval/run" && request.method === "POST") {
      const body = await readJson(request) as { cases?: Array<{ question?: string; expected_terms?: string[]; expected_source_ids?: string[] }> };
      const cases = Array.isArray(body.cases) ? body.cases : [];
      const results = cases.map((testCase, index) => {
        const matches = retrieve(testCase.question || "");
        const combined = matches.map((match) => `${match.id} ${match.text}`).join(" ").toLowerCase();
        const termsOk = (testCase.expected_terms || []).every((term) => combined.includes(term.toLowerCase()));
        const sourcesOk = (testCase.expected_source_ids || []).every((id) => matches.some((match) => match.id === id));
        return {
          id: `case-${index + 1}`,
          status: termsOk && sourcesOk ? "pass" : "block",
          matched_source_ids: matches.map((match) => match.id),
          missing_terms: (testCase.expected_terms || []).filter((term) => !combined.includes(term.toLowerCase())),
          missing_source_ids: (testCase.expected_source_ids || []).filter((id) => !matches.some((match) => match.id === id)),
        };
      });
      const passCount = results.filter((result) => result.status === "pass").length;
      return json({
        status: cases.length && passCount === cases.length ? "pass" : "block",
        pass_rate: cases.length ? passCount / cases.length : 0,
        results,
      });
    }

    if ((url.pathname === "/ingest" || url.pathname === "/deployments/register") && request.method === "POST") {
      return json({
        error: "Public live demo is read-only. The full FastAPI source supports write endpoints behind API-key protection.",
        source: gatewaySourceUrl,
      }, { status: 403 });
    }

    return json({ error: "Not found", docs: `${url.origin}/docs` }, { status: 404 });
  },
};
